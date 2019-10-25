import unittest
from nmigen import *
from nmigen.hdl.rec import Layout
from nmigen.back.pysim import *

from ..csr.bus import *


class ElementTestCase(unittest.TestCase):
    def test_layout_1_ro(self):
        elem = Element(1, "r")
        self.assertEqual(elem.width, 1)
        self.assertEqual(elem.access, Element.Access.R)
        self.assertEqual(elem.layout, Layout.cast([
            ("r_data", 1),
            ("r_stb", 1),
        ]))

    def test_layout_8_rw(self):
        elem = Element(8, access="rw")
        self.assertEqual(elem.width, 8)
        self.assertEqual(elem.access, Element.Access.RW)
        self.assertEqual(elem.layout, Layout.cast([
            ("r_data", 8),
            ("r_stb", 1),
            ("w_data", 8),
            ("w_stb", 1),
        ]))

    def test_layout_10_wo(self):
        elem = Element(10, "w")
        self.assertEqual(elem.width, 10)
        self.assertEqual(elem.access, Element.Access.W)
        self.assertEqual(elem.layout, Layout.cast([
            ("w_data", 10),
            ("w_stb", 1),
        ]))

    def test_layout_0_rw(self): # degenerate but legal case
        elem = Element(0, access=Element.Access.RW)
        self.assertEqual(elem.width, 0)
        self.assertEqual(elem.access, Element.Access.RW)
        self.assertEqual(elem.layout, Layout.cast([
            ("r_data", 0),
            ("r_stb", 1),
            ("w_data", 0),
            ("w_stb", 1),
        ]))

    def test_width_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Width must be a non-negative integer, not -1"):
            Element(-1, "rw")

    def test_access_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Access mode must be one of \"r\", \"w\", or \"rw\", not 'wo'"):
            Element(1, "wo")


class InterfaceTestCase(unittest.TestCase):
    def test_layout(self):
        iface = Interface(addr_width=12, data_width=8)
        self.assertEqual(iface.addr_width, 12)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("addr",    12),
            ("r_data",  8),
            ("r_stb",   1),
            ("w_data",  8),
            ("w_stb",   1),
        ]))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width must be a positive integer, not -1"):
            Interface(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive integer, not -1"):
            Interface(addr_width=16, data_width=-1)


class MultiplexerTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Multiplexer(addr_width=16, data_width=8)
        Fragment.get(self.dut, platform=None) # silence UnusedElaboratable

    def test_add_4b(self):
        self.assertEqual(self.dut.add(Element(4, "rw")),
                         (0, 1))

    def test_add_8b(self):
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (0, 1))

    def test_add_12b(self):
        self.assertEqual(self.dut.add(Element(12, "rw")),
                         (0, 2))

    def test_add_16b(self):
        self.assertEqual(self.dut.add(Element(16, "rw")),
                         (0, 2))

    def test_add_two(self):
        self.assertEqual(self.dut.add(Element(16, "rw")),
                         (0, 2))
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (2, 3))

    def test_add_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Width must be a non-negative integer, not -1"):
            Element(-1, "rw")

    def test_align_to(self):
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (0, 1))
        self.assertEqual(self.dut.align_to(2), 4)
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (4, 5))

    def test_sim(self):
        bus = self.dut.bus

        elem_4_r = Element(4, "r")
        self.dut.add(elem_4_r)
        elem_8_w = Element(8, "w")
        self.dut.add(elem_8_w)
        elem_16_rw = Element(16, "rw")
        self.dut.add(elem_16_rw)

        def sim_test():
            yield elem_4_r.r_data.eq(0xa)
            yield elem_16_rw.r_data.eq(0x5aa5)

            yield bus.addr.eq(0)
            yield bus.r_stb.eq(1)
            yield
            yield bus.r_stb.eq(0)
            self.assertEqual((yield elem_4_r.r_stb), 1)
            self.assertEqual((yield elem_16_rw.r_stb), 0)
            yield
            self.assertEqual((yield bus.r_data), 0xa)

            yield bus.addr.eq(2)
            yield bus.r_stb.eq(1)
            yield
            yield bus.r_stb.eq(0)
            self.assertEqual((yield elem_4_r.r_stb), 0)
            self.assertEqual((yield elem_16_rw.r_stb), 1)
            yield
            yield bus.addr.eq(3) # pipeline a read
            self.assertEqual((yield bus.r_data), 0xa5)

            yield bus.r_stb.eq(1)
            yield
            yield bus.r_stb.eq(0)
            self.assertEqual((yield elem_4_r.r_stb), 0)
            self.assertEqual((yield elem_16_rw.r_stb), 0)
            yield
            self.assertEqual((yield bus.r_data), 0x5a)

            yield bus.addr.eq(1)
            yield bus.w_data.eq(0x3d)
            yield bus.w_stb.eq(1)
            yield
            yield bus.w_stb.eq(0)
            yield
            self.assertEqual((yield elem_8_w.w_stb), 1)
            self.assertEqual((yield elem_8_w.w_data), 0x3d)
            self.assertEqual((yield elem_16_rw.w_stb), 0)

            yield bus.addr.eq(2)
            yield bus.w_data.eq(0x55)
            yield bus.w_stb.eq(1)
            yield
            self.assertEqual((yield elem_8_w.w_stb), 0)
            self.assertEqual((yield elem_16_rw.w_stb), 0)
            yield bus.addr.eq(3) # pipeline a write
            yield bus.w_data.eq(0xaa)
            yield
            self.assertEqual((yield elem_8_w.w_stb), 0)
            self.assertEqual((yield elem_16_rw.w_stb), 0)
            yield bus.w_stb.eq(0)
            yield
            self.assertEqual((yield elem_8_w.w_stb), 0)
            self.assertEqual((yield elem_16_rw.w_stb), 1)
            self.assertEqual((yield elem_16_rw.w_data), 0xaa55)

        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()


class MultiplexerAlignedTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Multiplexer(addr_width=16, data_width=8, alignment=2)
        Fragment.get(self.dut, platform=None) # silence UnusedElaboratable

    def test_add_two(self):
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (0, 4))
        self.assertEqual(self.dut.add(Element(16, "rw")),
                         (4, 8))

    def test_over_align_to(self):
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (0, 4))
        self.assertEqual(self.dut.align_to(3), 8)
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (8, 12))

    def test_under_align_to(self):
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (0, 4))
        self.assertEqual(self.dut.align_to(1), 4)
        self.assertEqual(self.dut.add(Element(8, "rw")),
                         (4, 8))

    def test_sim(self):
        bus = self.dut.bus

        elem_20_rw = Element(20, "rw")
        self.dut.add(elem_20_rw)

        def sim_test():
            yield bus.w_stb.eq(1)
            yield bus.addr.eq(0)
            yield bus.w_data.eq(0x55)
            yield
            self.assertEqual((yield elem_20_rw.w_stb), 0)
            yield bus.addr.eq(1)
            yield bus.w_data.eq(0xaa)
            yield
            self.assertEqual((yield elem_20_rw.w_stb), 0)
            yield bus.addr.eq(2)
            yield bus.w_data.eq(0x33)
            yield
            self.assertEqual((yield elem_20_rw.w_stb), 0)
            yield bus.addr.eq(3)
            yield bus.w_data.eq(0xdd)
            yield
            self.assertEqual((yield elem_20_rw.w_stb), 0)
            yield bus.w_stb.eq(0)
            yield
            self.assertEqual((yield elem_20_rw.w_stb), 1)
            self.assertEqual((yield elem_20_rw.w_data), 0x3aa55)

        with Simulator(self.dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()


class DecoderTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Decoder(addr_width=16, data_width=8)
        Fragment.get(self.dut, platform=None) # silence UnusedElaboratable

    def test_add_wrong_sub_bus(self):
        with self.assertRaisesRegex(TypeError,
                r"Subordinate bus must be an instance of csr\.Interface, not 1"):
            self.dut.add(1)

    def test_add_wrong_data_width(self):
        mux = Multiplexer(addr_width=10, data_width=16)
        Fragment.get(mux, platform=None) # silence UnusedElaboratable

        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 16, which is not the same as "
                r"multiplexer data width 8"):
            self.dut.add(mux.bus)

    def test_sim(self):
        mux_1  = Multiplexer(addr_width=10, data_width=8)
        self.dut.add(mux_1.bus)
        elem_1 = Element(8, "rw")
        mux_1.add(elem_1)

        mux_2  = Multiplexer(addr_width=10, data_width=8)
        self.dut.add(mux_2.bus)
        elem_2 = Element(8, "rw")
        mux_2.add(elem_2, addr=2)

        elem_1_addr, _, _ = self.dut.bus.memory_map.find_resource(elem_1)
        elem_2_addr, _, _ = self.dut.bus.memory_map.find_resource(elem_2)
        self.assertEqual(elem_1_addr, 0x0000)
        self.assertEqual(elem_2_addr, 0x0402)

        bus = self.dut.bus

        def sim_test():
            yield bus.addr.eq(elem_1_addr)
            yield bus.w_stb.eq(1)
            yield bus.w_data.eq(0x55)
            yield
            yield bus.w_stb.eq(0)
            yield
            self.assertEqual((yield elem_1.w_data), 0x55)

            yield bus.addr.eq(elem_2_addr)
            yield bus.w_stb.eq(1)
            yield bus.w_data.eq(0xaa)
            yield
            yield bus.w_stb.eq(0)
            yield
            self.assertEqual((yield elem_2.w_data), 0xaa)

            yield elem_1.r_data.eq(0x55)
            yield elem_2.r_data.eq(0xaa)

            yield bus.addr.eq(elem_1_addr)
            yield bus.r_stb.eq(1)
            yield
            yield bus.addr.eq(elem_2_addr)
            yield
            self.assertEqual((yield bus.r_data), 0x55)
            yield
            self.assertEqual((yield bus.r_data), 0xaa)

        m = Module()
        m.submodules += self.dut, mux_1, mux_2
        with Simulator(m, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
