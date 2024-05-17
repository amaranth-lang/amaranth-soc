# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import *

from amaranth_soc import csr
from amaranth_soc.memory import MemoryMap


class _MockRegister(wiring.Component):
    def __init__(self, width, access):
        super().__init__({"element": Out(csr.Element.Signature(width, access))})


class ElementSignatureTestCase(unittest.TestCase):
    def test_members_1_ro(self):
        sig = csr.Element.Signature(1, "r")
        self.assertEqual(sig.width, 1)
        self.assertEqual(sig.access, csr.Element.Access.R)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(1),
            "r_stb":  Out(1),
        }).members)

    def test_members_8_rw(self):
        sig = csr.Element.Signature(8, access="rw")
        self.assertEqual(sig.width, 8)
        self.assertEqual(sig.access, csr.Element.Access.RW)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(8),
            "r_stb":  Out(1),
            "w_data": Out(8),
            "w_stb":  Out(1),
        }).members)

    def test_members_10_wo(self):
        sig = csr.Element.Signature(10, "w")
        self.assertEqual(sig.width, 10)
        self.assertEqual(sig.access, csr.Element.Access.W)
        self.assertEqual(sig.members, wiring.Signature({
            "w_data": Out(10),
            "w_stb":  Out(1),
        }).members)

    def test_members_0_rw(self): # degenerate but legal case
        sig = csr.Element.Signature(0, access=csr.Element.Access.RW)
        self.assertEqual(sig.width, 0)
        self.assertEqual(sig.access, csr.Element.Access.RW)
        self.assertEqual(sig.members, wiring.Signature({
            "r_data": In(0),
            "r_stb":  Out(1),
            "w_data": Out(0),
            "w_stb":  Out(1),
        }).members)

    def test_create(self):
        sig  = csr.Element.Signature(8, "rw")
        elem = sig.create(path=("foo", "bar"))
        self.assertIsInstance(elem, csr.Element)
        self.assertEqual(elem.width, 8)
        self.assertEqual(elem.access, csr.Element.Access.RW)
        self.assertEqual(elem.r_stb.name, "foo__bar__r_stb")
        self.assertEqual(elem.signature, sig)

    def test_eq(self):
        self.assertEqual(csr.Element.Signature(8, "r"), csr.Element.Signature(8, "r"))
        self.assertEqual(csr.Element.Signature(8, "r"),
                         csr.Element.Signature(8, csr.Element.Access.R))
        # different width
        self.assertNotEqual(csr.Element.Signature(8, "r"), csr.Element.Signature(1, "r"))
        # different access mode
        self.assertNotEqual(csr.Element.Signature(8, "r"), csr.Element.Signature(8, "w"))
        self.assertNotEqual(csr.Element.Signature(8, "r"), csr.Element.Signature(8, "rw"))
        self.assertNotEqual(csr.Element.Signature(8, "w"), csr.Element.Signature(8, "rw"))

    def test_wrong_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Width must be a non-negative integer, not -1"):
            csr.Element.Signature(-1, "rw")

    def test_wrong_access(self):
        with self.assertRaisesRegex(ValueError,
                r"'wo' is not a valid Element.Access"):
            csr.Element.Signature(width=1, access="wo")


class ElementTestCase(unittest.TestCase):
    def test_simple(self):
        elem = csr.Element(8, "rw", path=("foo", "bar"))
        self.assertEqual(elem.width, 8)
        self.assertEqual(elem.access, csr.Element.Access.RW)
        self.assertEqual(elem.r_stb.name, "foo__bar__r_stb")


class SignatureTestCase(unittest.TestCase):
    def test_simple(self):
        sig = csr.Signature(addr_width=16, data_width=8)
        self.assertEqual(sig.addr_width, 16)
        self.assertEqual(sig.data_width, 8)
        self.assertEqual(sig.members, wiring.Signature({
            "addr":   Out(16),
            "r_data": In(8),
            "r_stb":  Out(1),
            "w_data": Out(8),
            "w_stb":  Out(1)
        }).members)

    def test_create(self):
        sig   = csr.Signature(addr_width=16, data_width=8)
        iface = sig.create(path=("foo", "bar"))
        self.assertIsInstance(iface, csr.Interface)
        self.assertEqual(iface.addr_width, 16)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.r_stb.name, "foo__bar__r_stb")
        self.assertEqual(iface.signature, sig)

    def test_eq(self):
        self.assertEqual(csr.Signature(addr_width=32, data_width=8),
                         csr.Signature(addr_width=32, data_width=8))
        # different addr_width
        self.assertNotEqual(csr.Signature(addr_width=16, data_width=16),
                            csr.Signature(addr_width=32, data_width=16))
        # different data_width
        self.assertNotEqual(csr.Signature(addr_width=32, data_width=8),
                            csr.Signature(addr_width=32, data_width=16))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Address width must be a positive integer, not -1"):
            csr.Signature(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Data width must be a positive integer, not -1"):
            csr.Signature(addr_width=16, data_width=-1)


class InterfaceTestCase(unittest.TestCase):
    def test_simple(self):
        iface = csr.Interface(addr_width=12, data_width=8, path=("foo", "bar"))
        self.assertEqual(iface.addr_width, 12)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.r_stb.name, "foo__bar__r_stb")

    def test_set_map(self):
        iface = csr.Interface(addr_width=12, data_width=8)
        memory_map = MemoryMap(addr_width=12, data_width=8)
        iface.memory_map = memory_map
        self.assertIs(iface.memory_map, memory_map)

    def test_get_map_none(self):
        iface = csr.Interface(addr_width=16, data_width=8)
        with self.assertRaisesRegex(AttributeError,
                r"csr.Interface\(.*\) does not have a memory map"):
            iface.memory_map

    def test_set_wrong_map(self):
        iface = csr.Interface(addr_width=16, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            iface.memory_map = "foo"

    def test_set_wrong_map_addr_width(self):
        iface = csr.Interface(addr_width=8, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has address width 7, which is not the same as bus interface address "
                r"width 8"):
            iface.memory_map = MemoryMap(addr_width=7, data_width=8)

    def test_set_wrong_map_data_width(self):
        iface = csr.Interface(addr_width=8, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has data width 7, which is not the same as bus interface data width "
                r"8"):
            iface.memory_map = MemoryMap(addr_width=8, data_width=7)


class MultiplexerTestCase(unittest.TestCase):
    def test_memory_map(self):
        reg_4_rw = _MockRegister(4, "rw")
        reg_8_rw = _MockRegister(8, "rw")

        memory_map = MemoryMap(addr_width=2, data_width=4)
        memory_map.add_resource(reg_4_rw, name=("reg_4_rw",), size=1)
        memory_map.add_resource(reg_8_rw, name=("reg_8_rw",), size=2)
        memory_map.freeze()

        dut = csr.Multiplexer(memory_map)

        self.assertIs(dut.bus.memory_map, memory_map)
        self.assertEqual(dut.bus.addr_width, 2)
        self.assertEqual(dut.bus.data_width, 4)

    def test_wrong_memory_map(self):
        with self.assertRaisesRegex(TypeError,
                r"CSR multiplexer memory map must be an instance of MemoryMap, not 'foo'"):
            csr.Multiplexer("foo")

    def test_wrong_memory_map_resource(self):
        class _Reg(wiring.Component):
            pass
        # wrong name
        map_0 = MemoryMap(addr_width=1, data_width=8)
        map_0.add_resource(_Reg({"foo": Out(csr.Element.Signature(8, "rw"))}), name=("a",), size=1)
        with self.assertRaisesRegex(AttributeError,
                r"Signature of CSR register \('a',\) must have a csr\.Element\.Signature member "
                r"named 'element' and oriented as wiring\.Out"):
            csr.Multiplexer(map_0)
        # wrong direction
        map_1 = MemoryMap(addr_width=1, data_width=8)
        map_1.add_resource(_Reg({"element": In(csr.Element.Signature(8, "rw"))}), name=("a",),
                           size=1)
        with self.assertRaisesRegex(AttributeError,
                r"Signature of CSR register \('a',\) must have a csr\.Element\.Signature member "
                r"named 'element' and oriented as wiring\.Out"):
            csr.Multiplexer(map_1)
        # wrong member type
        map_2 = MemoryMap(addr_width=1, data_width=8)
        map_2.add_resource(_Reg({"element": Out(unsigned(8))}), name=("a",), size=1)
        with self.assertRaisesRegex(AttributeError,
                r"Signature of CSR register \('a',\) must have a csr\.Element\.Signature member "
                r"named 'element' and oriented as wiring\.Out"):
            csr.Multiplexer(map_2)
        # wrong member signature
        map_3 = MemoryMap(addr_width=1, data_width=8)
        map_3.add_resource(_Reg({"element": Out(wiring.Signature({}))}), name=("a",), size=1)
        with self.assertRaisesRegex(AttributeError,
                r"Signature of CSR register \('a',\) must have a csr\.Element\.Signature member "
                r"named 'element' and oriented as wiring\.Out"):
            csr.Multiplexer(map_3)

    def test_wrong_memory_map_windows(self):
        memory_map_0 = MemoryMap(addr_width=1, data_width=8)
        memory_map_1 = MemoryMap(addr_width=1, data_width=8)
        memory_map_0.add_window(memory_map_1)
        with self.assertRaisesRegex(ValueError, r"CSR multiplexer memory map cannot have windows"):
            csr.Multiplexer(memory_map_0)

    def test_sim(self):
        for shadow_overlaps in [None, 0, 1]:
            with self.subTest(shadow_overlaps=shadow_overlaps):
                reg_4_r   = _MockRegister( 4, "r")
                reg_8_w   = _MockRegister( 8, "w")
                reg_16_rw = _MockRegister(16, "rw")

                memory_map = MemoryMap(addr_width=16, data_width=8)
                memory_map.add_resource(reg_4_r,   name=("reg_4_r",),   size=1)
                memory_map.add_resource(reg_8_w,   name=("reg_8_w",),   size=1)
                memory_map.add_resource(reg_16_rw, name=("reg_16_rw",), size=2)

                dut = csr.Multiplexer(memory_map, shadow_overlaps=shadow_overlaps)
                bus = dut.bus

                def sim_test():
                    yield reg_4_r.element.r_data.eq(0xa)
                    yield reg_16_rw.element.r_data.eq(0x5aa5)

                    yield bus.addr.eq(0)
                    yield bus.r_stb.eq(1)
                    yield Tick()
                    self.assertEqual((yield reg_4_r.element.r_stb), 1)
                    self.assertEqual((yield reg_16_rw.element.r_stb), 0)
                    self.assertEqual((yield bus.r_data), 0xa)

                    yield bus.addr.eq(2)
                    yield Tick()
                    self.assertEqual((yield reg_4_r.element.r_stb), 0)
                    self.assertEqual((yield reg_16_rw.element.r_stb), 1)
                    self.assertEqual((yield bus.r_data), 0xa5)

                    yield bus.addr.eq(3) # pipeline a read
                    yield Tick()
                    self.assertEqual((yield reg_4_r.element.r_stb), 0)
                    self.assertEqual((yield reg_16_rw.element.r_stb), 0)
                    self.assertEqual((yield bus.r_data), 0x5a)
                    yield bus.r_stb.eq(0)
                    yield Delay()

                    yield bus.addr.eq(1)
                    yield bus.w_data.eq(0x3d)
                    yield bus.w_stb.eq(1)
                    yield Tick()
                    self.assertEqual((yield reg_8_w.element.w_stb), 1)
                    self.assertEqual((yield reg_8_w.element.w_data), 0x3d)
                    self.assertEqual((yield reg_16_rw.element.w_stb), 0)

                    yield bus.w_stb.eq(0)
                    yield bus.addr.eq(2) # change address
                    yield Tick()
                    self.assertEqual((yield reg_8_w.element.w_stb), 0)

                    yield bus.addr.eq(2)
                    yield bus.w_data.eq(0x55)
                    yield bus.w_stb.eq(1)
                    yield Tick()
                    self.assertEqual((yield reg_8_w.element.w_stb), 0)
                    self.assertEqual((yield reg_16_rw.element.w_stb), 0)
                    yield bus.addr.eq(3) # pipeline a write
                    yield bus.w_data.eq(0xaa)
                    yield Tick()
                    self.assertEqual((yield reg_8_w.element.w_stb), 0)
                    self.assertEqual((yield reg_16_rw.element.w_stb), 1)
                    self.assertEqual((yield reg_16_rw.element.w_data), 0xaa55)

                    yield bus.addr.eq(2)
                    yield bus.r_stb.eq(1)
                    yield bus.w_data.eq(0x66)
                    yield bus.w_stb.eq(1)
                    yield Tick()
                    self.assertEqual((yield reg_16_rw.element.r_stb), 1)
                    self.assertEqual((yield reg_16_rw.element.w_stb), 0)
                    self.assertEqual((yield bus.r_data), 0xa5)
                    yield bus.addr.eq(3) # pipeline a read and a write
                    yield bus.w_data.eq(0xbb)
                    yield Tick()
                    self.assertEqual((yield bus.r_data), 0x5a)
                    self.assertEqual((yield reg_16_rw.element.r_stb), 0)
                    self.assertEqual((yield reg_16_rw.element.w_stb), 1)
                    self.assertEqual((yield reg_16_rw.element.w_data), 0xbb66)

                sim = Simulator(dut)
                sim.add_clock(1e-6)
                sim.add_testbench(sim_test)
                with sim.write_vcd(vcd_file=open("test.vcd", "w")):
                    sim.run()


class MultiplexerAlignedTestCase(unittest.TestCase):
    def test_sim(self):
        for shadow_overlaps in [None, 0, 1]:
            with self.subTest(shadow_overlaps=shadow_overlaps):
                reg_20_rw = _MockRegister(20, "rw")
                memory_map = MemoryMap(addr_width=16, data_width=8, alignment=2)
                memory_map.add_resource(reg_20_rw, name=("reg_20_rw",), size=3)

                dut = csr.Multiplexer(memory_map, shadow_overlaps=shadow_overlaps)
                bus = dut.bus

                def sim_test():
                    yield bus.w_stb.eq(1)
                    yield bus.addr.eq(0)
                    yield bus.w_data.eq(0x55)
                    yield Tick()
                    self.assertEqual((yield reg_20_rw.element.w_stb), 0)
                    yield bus.addr.eq(1)
                    yield bus.w_data.eq(0xaa)
                    yield Tick()
                    self.assertEqual((yield reg_20_rw.element.w_stb), 0)
                    yield bus.addr.eq(2)
                    yield bus.w_data.eq(0x33)
                    yield Tick()
                    self.assertEqual((yield reg_20_rw.element.w_stb), 0)
                    yield bus.addr.eq(3)
                    yield bus.w_data.eq(0xdd)
                    yield Tick()
                    self.assertEqual((yield reg_20_rw.element.w_stb), 1)
                    self.assertEqual((yield reg_20_rw.element.w_data), 0x3aa55)

                sim = Simulator(dut)
                sim.add_clock(1e-6)
                sim.add_testbench(sim_test)
                with sim.write_vcd(vcd_file=open("test.vcd", "w")):
                    sim.run()


class DecoderTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = csr.Decoder(addr_width=16, data_width=8)

    def test_align_to(self):
        sub_1 = csr.Interface(addr_width=10, data_width=8)
        sub_1.memory_map = MemoryMap(addr_width=10, data_width=8)
        self.assertEqual(self.dut.add(sub_1), (0, 0x400, 1))

        self.assertEqual(self.dut.align_to(12), 0x1000)
        self.assertEqual(self.dut.align_to(alignment=12), 0x1000)

        sub_2 = csr.Interface(addr_width=10, data_width=8)
        sub_2.memory_map = MemoryMap(addr_width=10, data_width=8)
        self.assertEqual(self.dut.add(sub_2), (0x1000, 0x1400, 1))

    def test_add_wrong_sub_bus(self):
        with self.assertRaisesRegex(TypeError,
                r"Subordinate bus must be an instance of csr\.Interface, not 1"):
            self.dut.add(sub_bus=1)

    def test_add_wrong_data_width(self):
        mux = csr.Multiplexer(MemoryMap(addr_width=10, data_width=16))
        Fragment.get(mux, platform=None) # silence UnusedElaboratable

        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 16, which is not the same as "
                r"decoder data width 8"):
            self.dut.add(mux.bus)

    def test_add_wrong_out_of_bounds(self):
        iface = csr.Interface(addr_width=17, data_width=8)
        iface.memory_map = MemoryMap(addr_width=17, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x0\.\.0x20000 out of bounds for memory map spanning "
                r"range 0x0\.\.0x10000 \(16 address bits\)"):
            self.dut.add(iface)

    def test_sim(self):
        reg_1 = _MockRegister(8, "rw")
        reg_2 = _MockRegister(8, "rw")

        memory_map_1 = MemoryMap(addr_width=10, data_width=8)
        memory_map_1.add_resource(reg_1, name=("reg_1",), size=1)

        memory_map_2 = MemoryMap(addr_width=10, data_width=8)
        memory_map_2.add_resource(reg_2, name=("reg_2",), size=1, addr=2)

        mux_1 = csr.Multiplexer(memory_map_1)
        mux_2 = csr.Multiplexer(memory_map_2)

        self.dut.add(mux_1.bus)
        self.dut.add(mux_2.bus)

        reg_1_info = self.dut.bus.memory_map.find_resource(reg_1)
        reg_2_info = self.dut.bus.memory_map.find_resource(reg_2)
        reg_1_addr = reg_1_info.start
        reg_2_addr = reg_2_info.start
        self.assertEqual(reg_1_addr, 0x0000)
        self.assertEqual(reg_2_addr, 0x0402)

        bus = self.dut.bus

        def sim_test():
            yield bus.addr.eq(reg_1_addr)
            yield bus.w_stb.eq(1)
            yield bus.w_data.eq(0x55)
            yield Tick()
            yield bus.w_stb.eq(0)
            yield Tick()
            self.assertEqual((yield reg_1.element.w_data), 0x55)

            yield bus.addr.eq(reg_2_addr)
            yield bus.w_stb.eq(1)
            yield bus.w_data.eq(0xaa)
            yield Tick()
            yield bus.w_stb.eq(0)
            yield Tick()
            self.assertEqual((yield reg_2.element.w_data), 0xaa)

            yield reg_1.element.r_data.eq(0x55)
            yield reg_2.element.r_data.eq(0xaa)

            yield bus.addr.eq(reg_1_addr)
            yield bus.r_stb.eq(1)
            yield Tick()
            yield bus.addr.eq(reg_2_addr)
            yield Delay()
            self.assertEqual((yield bus.r_data), 0x55)
            yield Tick()
            self.assertEqual((yield bus.r_data), 0xaa)

        m = Module()
        m.submodules += self.dut, mux_1, mux_2
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()
