# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.hdl.rec import *
from nmigen.back.pysim import *

from ..wishbone.bus import *
from ..memory import MemoryMap


class InterfaceTestCase(unittest.TestCase):
    def test_simple(self):
        iface = Interface(addr_width=32, data_width=8)
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   32, DIR_FANOUT),
            ("dat_w", 8,  DIR_FANOUT),
            ("dat_r", 8,  DIR_FANIN),
            ("sel",   1,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
        ]))

    def test_granularity(self):
        iface = Interface(addr_width=30, data_width=32, granularity=8)
        self.assertEqual(iface.addr_width, 30)
        self.assertEqual(iface.data_width, 32)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   30, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",   4,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
        ]))

    def test_features(self):
        iface = Interface(addr_width=32, data_width=32,
                          features={"rty", "err", "stall", "lock", "cti", "bte"})
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   32, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",   1,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
            ("err",   1,  DIR_FANIN),
            ("rty",   1,  DIR_FANIN),
            ("stall", 1,  DIR_FANIN),
            ("lock",  1,  DIR_FANOUT),
            ("cti",   CycleType,    DIR_FANOUT),
            ("bte",   BurstTypeExt, DIR_FANOUT),
        ]))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width must be a non-negative integer, not -1"):
            Interface(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be one of 8, 16, 32, 64, not 7"):
            Interface(addr_width=0, data_width=7)

    def test_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity must be one of 8, 16, 32, 64, not 7"):
            Interface(addr_width=0, data_width=32, granularity=7)

    def test_wrong_granularity_wide(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity 32 may not be greater than data width 8"):
            Interface(addr_width=0, data_width=8, granularity=32)

    def test_wrong_features(self):
        with self.assertRaisesRegex(ValueError,
                r"Optional signal\(s\) 'foo' are not supported"):
            Interface(addr_width=0, data_width=8, features={"foo"})

    def test_get_map_wrong(self):
        iface = Interface(addr_width=0, data_width=8)
        with self.assertRaisesRegex(NotImplementedError,
                r"Bus interface \(rec iface adr dat_w dat_r sel cyc stb we ack\) does "
                r"not have a memory map"):
            iface.memory_map

    def test_get_map_frozen(self):
        iface = Interface(addr_width=1, data_width=8)
        iface.memory_map = MemoryMap(addr_width=1, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen\. Address width cannot be extended "
                r"further"):
            iface.memory_map.addr_width = 2

    def test_set_map_wrong(self):
        iface = Interface(addr_width=0, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            iface.memory_map = "foo"

    def test_set_map_wrong_data_width(self):
        iface = Interface(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has data width 32, which is not the same as bus "
                r"interface granularity 8"):
            iface.memory_map = MemoryMap(addr_width=32, data_width=32)

    def test_set_map_wrong_addr_width(self):
        iface = Interface(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has address width 30, which is not the same as bus "
                r"interface address width 32 \(30 address bits \+ 2 granularity bits\)"):
            iface.memory_map = MemoryMap(addr_width=30, data_width=8)


class DecoderTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Decoder(addr_width=31, data_width=32, granularity=16)

    def test_add_align_to(self):
        sub_1 = Interface(addr_width=15, data_width=32, granularity=16)
        sub_1.memory_map = MemoryMap(addr_width=16, data_width=16)
        sub_2 = Interface(addr_width=15, data_width=32, granularity=16)
        sub_2.memory_map = MemoryMap(addr_width=16, data_width=16)
        self.assertEqual(self.dut.add(sub_1), (0x00000000, 0x00010000, 1))
        self.assertEqual(self.dut.align_to(18), 0x000040000)
        self.assertEqual(self.dut.align_to(alignment=18), 0x000040000)
        self.assertEqual(self.dut.add(sub_2), (0x00040000, 0x00050000, 1))

    def test_add_extend(self):
        sub = Interface(addr_width=31, data_width=32, granularity=16)
        sub.memory_map = MemoryMap(addr_width=32, data_width=16)
        self.assertEqual(self.dut.add(sub, addr=1, extend=True), (1, 0x100000001, 1))
        self.assertEqual(self.dut.bus.addr_width, 32)

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Subordinate bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add(sub_bus="foo")

    def test_add_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has granularity 32, which is greater than "
                r"the decoder granularity 16"):
            self.dut.add(Interface(addr_width=15, data_width=32, granularity=32))

    def test_add_wrong_width_dense(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 16, which is not the same as decoder "
                r"data width 32 \(required for dense address translation\)"):
            self.dut.add(Interface(addr_width=15, data_width=16, granularity=16))

    def test_add_wrong_granularity_sparse(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 64, which is not the same as subordinate "
                r"bus granularity 16 \(required for sparse address translation\)"):
            self.dut.add(Interface(addr_width=15, data_width=64, granularity=16), sparse=True)

    def test_add_wrong_optional_output(self):
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has optional output 'err', but the decoder does "
                r"not have a corresponding input"):
            self.dut.add(Interface(addr_width=15, data_width=32, granularity=16, features={"err"}))

    def test_add_wrong_out_of_bounds(self):
        sub = Interface(addr_width=31, data_width=32, granularity=16)
        sub.memory_map = MemoryMap(addr_width=32, data_width=16)
        with self.assertRaisesRegex(ValueError,
            r"Address range 0x1\.\.0x100000001 out of bounds for memory map spanning "
            r"range 0x0\.\.0x100000000 \(32 address bits\)"):
            self.dut.add(sub, addr=1)


class DecoderSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = Decoder(addr_width=30, data_width=32, granularity=8,
                      features={"err", "rty", "stall", "lock", "cti", "bte"})
        sub_1 = Interface(addr_width=14, data_width=32, granularity=8)
        sub_1.memory_map = MemoryMap(addr_width=16, data_width=8)
        dut.add(sub_1, addr=0x10000)
        sub_2 = Interface(addr_width=14, data_width=32, granularity=8,
                          features={"err", "rty", "stall", "lock", "cti", "bte"})
        sub_2.memory_map = MemoryMap(addr_width=16, data_width=8)
        dut.add(sub_2)

        def sim_test():
            yield dut.bus.adr.eq(0x10400 >> 2)
            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield dut.bus.sel.eq(0b11)
            yield dut.bus.dat_w.eq(0x12345678)
            yield dut.bus.lock.eq(1)
            yield dut.bus.cti.eq(CycleType.INCR_BURST)
            yield dut.bus.bte.eq(BurstTypeExt.WRAP_4)
            yield sub_1.ack.eq(1)
            yield sub_1.dat_r.eq(0xabcdef01)
            yield sub_2.dat_r.eq(0x5678abcd)
            yield Delay(1e-6)
            self.assertEqual((yield sub_1.adr), 0x400 >> 2)
            self.assertEqual((yield sub_1.cyc), 1)
            self.assertEqual((yield sub_2.cyc), 0)
            self.assertEqual((yield sub_1.stb), 1)
            self.assertEqual((yield sub_1.sel), 0b11)
            self.assertEqual((yield sub_1.dat_w), 0x12345678)
            self.assertEqual((yield dut.bus.ack), 1)
            self.assertEqual((yield dut.bus.err), 0)
            self.assertEqual((yield dut.bus.rty), 0)
            self.assertEqual((yield dut.bus.dat_r), 0xabcdef01)

            yield dut.bus.adr.eq(0x20400 >> 2)
            yield sub_1.ack.eq(0)
            yield sub_2.err.eq(1)
            yield sub_2.rty.eq(1)
            yield sub_2.stall.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield sub_2.adr), 0x400 >> 2)
            self.assertEqual((yield sub_1.cyc), 0)
            self.assertEqual((yield sub_2.cyc), 1)
            self.assertEqual((yield sub_1.stb), 1)
            self.assertEqual((yield sub_1.sel), 0b11)
            self.assertEqual((yield sub_1.dat_w), 0x12345678)
            self.assertEqual((yield sub_2.lock), 1)
            self.assertEqual((yield sub_2.cti), CycleType.INCR_BURST.value)
            self.assertEqual((yield sub_2.bte), BurstTypeExt.WRAP_4.value)
            self.assertEqual((yield dut.bus.ack), 0)
            self.assertEqual((yield dut.bus.err), 1)
            self.assertEqual((yield dut.bus.rty), 1)
            self.assertEqual((yield dut.bus.stall), 1)
            self.assertEqual((yield dut.bus.dat_r), 0x5678abcd)

        sim = Simulator(dut)
        sim.add_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_addr_translate(self):
        class AddressLoopback(Elaboratable):
            def __init__(self, **kwargs):
                self.bus = Interface(**kwargs)

            def elaborate(self, platform):
                m = Module()

                for index, sel_bit in enumerate(self.bus.sel):
                    with m.If(sel_bit):
                        segment = self.bus.dat_r.word_select(index, self.bus.granularity)
                        m.d.comb += segment.eq(self.bus.adr + index)

                return m

        dut = Decoder(addr_width=20, data_width=32, granularity=16)
        loop_1 = AddressLoopback(addr_width=7, data_width=32, granularity=16)
        loop_1.bus.memory_map = MemoryMap(addr_width=8, data_width=16)
        self.assertEqual(dut.add(loop_1.bus, addr=0x10000),
                         (0x10000, 0x10100, 1))
        loop_2 = AddressLoopback(addr_width=6, data_width=32, granularity=8)
        loop_2.bus.memory_map = MemoryMap(addr_width=8, data_width=8)
        self.assertEqual(dut.add(loop_2.bus, addr=0x20000),
                         (0x20000, 0x20080, 2))
        loop_3 = AddressLoopback(addr_width=8, data_width=16, granularity=16)
        loop_3.bus.memory_map = MemoryMap(addr_width=8, data_width=16)
        self.assertEqual(dut.add(loop_3.bus, addr=0x30000, sparse=True),
                         (0x30000, 0x30100, 1))
        loop_4 = AddressLoopback(addr_width=8, data_width=8,  granularity=8)
        loop_4.bus.memory_map = MemoryMap(addr_width=8, data_width=8)
        self.assertEqual(dut.add(loop_4.bus, addr=0x40000, sparse=True),
                         (0x40000, 0x40100, 1))

        def sim_test():
            yield dut.bus.cyc.eq(1)

            yield dut.bus.adr.eq(0x10010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00090008)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00000008)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00090000)

            yield dut.bus.adr.eq(0x20010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x13121110)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00001110)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x13120000)

            yield dut.bus.adr.eq(0x30010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0008)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0008)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0000)

            yield dut.bus.adr.eq(0x30012 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x0009)

            yield dut.bus.adr.eq(0x40010 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x08)

            yield dut.bus.sel.eq(0b01)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x08)

            yield dut.bus.sel.eq(0b10)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x00)

            yield dut.bus.adr.eq(0x40012 >> 1)

            yield dut.bus.sel.eq(0b11)
            yield Delay(1e-6)
            self.assertEqual((yield dut.bus.dat_r), 0x09)

        m = Module()
        m.submodules += dut, loop_1, loop_2, loop_3, loop_4
        sim = Simulator(m)
        sim.add_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_coarse_granularity(self):
        dut = Decoder(addr_width=3, data_width=32)
        sub = Interface(addr_width=2, data_width=32)
        sub.memory_map = MemoryMap(addr_width=2, data_width=32)
        dut.add(sub)

        def sim_test():
            yield dut.bus.cyc.eq(1)

            yield dut.bus.adr.eq(0x0)
            yield Delay(1e-6)
            self.assertEqual((yield sub.cyc), 1)

            yield dut.bus.adr.eq(0x4)
            yield Delay(1e-6)
            self.assertEqual((yield sub.cyc), 0)

        sim = Simulator(dut)
        sim.add_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class ArbiterTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = Arbiter(addr_width=31, data_width=32, granularity=16,
                           features={"err"})

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Initiator bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add(intr_bus="foo")

    def test_add_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has address width 15, which is not the same as arbiter "
                r"address width 31"):
            self.dut.add(Interface(addr_width=15, data_width=32, granularity=16))

    def test_add_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has granularity 8, which is lesser than "
                r"the arbiter granularity 16"):
            self.dut.add(Interface(addr_width=31, data_width=32, granularity=8))

    def test_add_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has data width 16, which is not the same as arbiter "
                r"data width 32"):
            self.dut.add(Interface(addr_width=31, data_width=16, granularity=16))

    def test_add_wrong_optional_output(self):
        with self.assertRaisesRegex(ValueError,
                r"Arbiter has optional output 'err', but the initiator bus does "
                r"not have a corresponding input"):
            self.dut.add(Interface(addr_width=31, data_width=32, granularity=16))


class ArbiterSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = Arbiter(addr_width=30, data_width=32, granularity=8,
                      features={"err", "rty", "stall", "lock", "cti", "bte"})
        intr_1 = Interface(addr_width=30, data_width=32, granularity=8,
                           features={"err", "rty"})
        dut.add(intr_1)
        intr_2 = Interface(addr_width=30, data_width=32, granularity=16,
                      features={"err", "rty", "stall", "lock", "cti", "bte"})
        dut.add(intr_2)

        def sim_test():
            yield intr_1.adr.eq(0x7ffffffc >> 2)
            yield intr_1.cyc.eq(1)
            yield intr_1.stb.eq(1)
            yield intr_1.sel.eq(0b1111)
            yield intr_1.we.eq(1)
            yield intr_1.dat_w.eq(0x12345678)
            yield dut.bus.dat_r.eq(0xabcdef01)
            yield dut.bus.ack.eq(1)
            yield dut.bus.err.eq(1)
            yield dut.bus.rty.eq(1)
            yield Delay(1e-7)
            self.assertEqual((yield dut.bus.adr), 0x7ffffffc >> 2)
            self.assertEqual((yield dut.bus.cyc), 1)
            self.assertEqual((yield dut.bus.stb), 1)
            self.assertEqual((yield dut.bus.sel), 0b1111)
            self.assertEqual((yield dut.bus.we), 1)
            self.assertEqual((yield dut.bus.dat_w), 0x12345678)
            self.assertEqual((yield dut.bus.lock), 0)
            self.assertEqual((yield dut.bus.cti), CycleType.CLASSIC.value)
            self.assertEqual((yield dut.bus.bte), BurstTypeExt.LINEAR.value)
            self.assertEqual((yield intr_1.dat_r), 0xabcdef01)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_1.err), 1)
            self.assertEqual((yield intr_1.rty), 1)

            yield intr_1.cyc.eq(0)
            yield intr_2.adr.eq(0xe0000000 >> 2)
            yield intr_2.cyc.eq(1)
            yield intr_2.stb.eq(1)
            yield intr_2.sel.eq(0b10)
            yield intr_2.we.eq(1)
            yield intr_2.dat_w.eq(0x43218765)
            yield intr_2.lock.eq(0)
            yield intr_2.cti.eq(CycleType.INCR_BURST)
            yield intr_2.bte.eq(BurstTypeExt.WRAP_4)
            yield Tick()

            yield dut.bus.stall.eq(0)
            yield Delay(1e-7)
            self.assertEqual((yield dut.bus.adr), 0xe0000000 >> 2)
            self.assertEqual((yield dut.bus.cyc), 1)
            self.assertEqual((yield dut.bus.stb), 1)
            self.assertEqual((yield dut.bus.sel), 0b1100)
            self.assertEqual((yield dut.bus.we), 1)
            self.assertEqual((yield dut.bus.dat_w), 0x43218765)
            self.assertEqual((yield dut.bus.lock), 0)
            self.assertEqual((yield dut.bus.cti), CycleType.INCR_BURST.value)
            self.assertEqual((yield dut.bus.bte), BurstTypeExt.WRAP_4.value)
            self.assertEqual((yield intr_2.dat_r), 0xabcdef01)
            self.assertEqual((yield intr_2.ack), 1)
            self.assertEqual((yield intr_2.err), 1)
            self.assertEqual((yield intr_2.rty), 1)
            self.assertEqual((yield intr_2.stall), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_lock(self):
        dut = Arbiter(addr_width=30, data_width=32, features={"lock"})
        intr_1 = Interface(addr_width=30, data_width=32, features={"lock"})
        dut.add(intr_1)
        intr_2 = Interface(addr_width=30, data_width=32, features={"lock"})
        dut.add(intr_2)

        def sim_test():
            yield intr_1.cyc.eq(1)
            yield intr_1.lock.eq(1)
            yield intr_2.cyc.eq(1)
            yield dut.bus.ack.eq(1)
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_2.ack), 0)

            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_2.ack), 0)

            yield intr_1.lock.eq(0)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 0)
            self.assertEqual((yield intr_2.ack), 1)

            yield intr_2.cyc.eq(0)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_2.ack), 0)

            yield intr_1.stb.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_2.ack), 0)

            yield intr_1.stb.eq(0)
            yield intr_2.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 0)
            self.assertEqual((yield intr_2.ack), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_stall(self):
        dut = Arbiter(addr_width=30, data_width=32, features={"stall"})
        intr_1 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(intr_1)
        intr_2 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(intr_2)

        def sim_test():
            yield intr_1.cyc.eq(1)
            yield intr_2.cyc.eq(1)
            yield dut.bus.stall.eq(0)
            yield Delay(1e-6)
            self.assertEqual((yield intr_1.stall), 0)
            self.assertEqual((yield intr_2.stall), 1)

            yield dut.bus.stall.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield intr_1.stall), 1)
            self.assertEqual((yield intr_2.stall), 1)

        sim = Simulator(dut)
        sim.add_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_stall_compat(self):
        dut = Arbiter(addr_width=30, data_width=32)
        intr_1 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(intr_1)
        intr_2 = Interface(addr_width=30, data_width=32, features={"stall"})
        dut.add(intr_2)

        def sim_test():
            yield intr_1.cyc.eq(1)
            yield intr_2.cyc.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield intr_1.stall), 1)
            self.assertEqual((yield intr_2.stall), 1)

            yield dut.bus.ack.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield intr_1.stall), 0)
            self.assertEqual((yield intr_2.stall), 1)

        sim = Simulator(dut)
        sim.add_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_roundrobin(self):
        dut = Arbiter(addr_width=30, data_width=32)
        intr_1 = Interface(addr_width=30, data_width=32)
        dut.add(intr_1)
        intr_2 = Interface(addr_width=30, data_width=32)
        dut.add(intr_2)
        intr_3 = Interface(addr_width=30, data_width=32)
        dut.add(intr_3)

        def sim_test():
            yield intr_1.cyc.eq(1)
            yield intr_2.cyc.eq(0)
            yield intr_3.cyc.eq(1)
            yield dut.bus.ack.eq(1)
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_2.ack), 0)
            self.assertEqual((yield intr_3.ack), 0)

            yield intr_1.cyc.eq(0)
            yield intr_2.cyc.eq(0)
            yield intr_3.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 0)
            self.assertEqual((yield intr_2.ack), 0)
            self.assertEqual((yield intr_3.ack), 1)

            yield intr_1.cyc.eq(1)
            yield intr_2.cyc.eq(1)
            yield intr_3.cyc.eq(0)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 1)
            self.assertEqual((yield intr_2.ack), 0)
            self.assertEqual((yield intr_3.ack), 0)

            yield intr_1.cyc.eq(0)
            yield intr_2.cyc.eq(1)
            yield intr_3.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 0)
            self.assertEqual((yield intr_2.ack), 1)
            self.assertEqual((yield intr_3.ack), 0)

            yield intr_1.cyc.eq(1)
            yield intr_2.cyc.eq(0)
            yield intr_3.cyc.eq(1)
            yield Tick()
            yield Delay(1e-7)
            self.assertEqual((yield intr_1.ack), 0)
            self.assertEqual((yield intr_2.ack), 0)
            self.assertEqual((yield intr_3.ack), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()
