# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.sim import *

from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap


class SignatureTestCase(unittest.TestCase):
    def test_simple(self):
        sig = wishbone.Signature(addr_width=32, data_width=8)
        self.assertEqual(sig.addr_width, 32)
        self.assertEqual(sig.data_width,  8)
        self.assertEqual(sig.granularity, 8)
        self.assertEqual(sig.members, Signature({
            "adr":   Out(32),
            "dat_w": Out(8),
            "dat_r": In(8),
            "sel":   Out(1),
            "cyc":   Out(1),
            "stb":   Out(1),
            "we":    Out(1),
            "ack":   In(1),
        }).members)

    def test_granularity(self):
        sig = wishbone.Signature(addr_width=30, data_width=32, granularity=8)
        self.assertEqual(sig.addr_width, 30)
        self.assertEqual(sig.data_width, 32)
        self.assertEqual(sig.granularity, 8)
        self.assertEqual(sig.members, Signature({
            "adr":   Out(30),
            "dat_w": Out(32),
            "dat_r": In(32),
            "sel":   Out(4),
            "cyc":   Out(1),
            "stb":   Out(1),
            "we":    Out(1),
            "ack":   In(1),
        }).members)

    def test_features(self):
        sig = wishbone.Signature(addr_width=32, data_width=32,
                                 features={"rty", "err", "stall", "lock", "cti", "bte"})
        self.assertEqual(sig.features, {
            wishbone.Feature.RTY,
            wishbone.Feature.ERR,
            wishbone.Feature.STALL,
            wishbone.Feature.LOCK,
            wishbone.Feature.CTI,
            wishbone.Feature.BTE,
        })
        self.assertEqual(sig.members, Signature({
            "adr":   Out(32),
            "dat_w": Out(32),
            "dat_r": In(32),
            "sel":   Out(1),
            "cyc":   Out(1),
            "stb":   Out(1),
            "we":    Out(1),
            "ack":   In(1),
            "err":   In(1),
            "rty":   In(1),
            "stall": In(1),
            "lock":  Out(1),
            "cti":   Out(wishbone.CycleType),
            "bte":   Out(wishbone.BurstTypeExt),
        }).members)

    def test_create(self):
        sig   = wishbone.Signature(addr_width=32, data_width=16, granularity=8)
        iface = sig.create(path=("iface",))
        self.assertIsInstance(iface, wishbone.Interface)
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 16)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.signature, sig)

    def test_eq(self):
        self.assertEqual(wishbone.Signature(addr_width=32, data_width=8, features={"err"}),
                         wishbone.Signature(addr_width=32, data_width=8, features={"err"}))
        # different addr_width
        self.assertNotEqual(wishbone.Signature(addr_width=16, data_width=16, granularity=8),
                            wishbone.Signature(addr_width=32, data_width=16, granularity=8))
        # different data_width
        self.assertNotEqual(wishbone.Signature(addr_width=32, data_width=8, granularity=8),
                            wishbone.Signature(addr_width=32, data_width=16, granularity=8))
        # different granularity
        self.assertNotEqual(wishbone.Signature(addr_width=32, data_width=16, granularity=8),
                            wishbone.Signature(addr_width=32, data_width=16, granularity=16))
        self.assertNotEqual(wishbone.Signature(addr_width=32, data_width=16, granularity=8),
                            wishbone.Signature(addr_width=32, data_width=16))
        # different features
        self.assertNotEqual(wishbone.Signature(addr_width=32, data_width=16, granularity=8),
                            wishbone.Signature(addr_width=32, data_width=16, granularity=8,
                                               features={"err"}))
        self.assertNotEqual(wishbone.Signature(addr_width=32, data_width=16, granularity=8,
                                               features={"rty"}),
                            wishbone.Signature(addr_width=32, data_width=16, granularity=8,
                                               features={"err"}))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Address width must be a non-negative integer, not -1"):
            wishbone.Signature(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be one of 8, 16, 32, 64, not 7"):
            wishbone.Signature(addr_width=0, data_width=7)

    def test_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity must be one of 8, 16, 32, 64, not 7"):
            wishbone.Signature(addr_width=0, data_width=32, granularity=7)

    def test_wrong_granularity_wide(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity 32 may not be greater than data width 8"):
            wishbone.Signature(addr_width=0, data_width=8, granularity=32)

    def test_wrong_features(self):
        with self.assertRaisesRegex(ValueError, r"'foo' is not a valid Feature"):
            wishbone.Signature(addr_width=0, data_width=8, features={"foo"})


class InterfaceTestCase(unittest.TestCase):
    def test_simple(self):
        iface = wishbone.Interface(addr_width=32, data_width=8, features={"err"})
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.features, {wishbone.Feature.ERR})

    def test_set_map(self):
        iface = wishbone.Interface(addr_width=15, data_width=16, granularity=8)
        memory_map = MemoryMap(addr_width=16, data_width=8)
        iface.memory_map = memory_map
        self.assertIs(iface.memory_map, memory_map)

    def test_get_map_none(self):
        iface = wishbone.Interface(addr_width=8, data_width=8)
        with self.assertRaisesRegex(AttributeError,
                r"wishbone.Interface\(.*\) does not have a memory map"):
            iface.memory_map

    def test_set_wrong_map(self):
        iface = wishbone.Interface(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            iface.memory_map = "foo"

    def test_set_wrong_map_data_width(self):
        iface = wishbone.Interface(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has data width 32, which is not the same as bus "
                r"interface granularity 8"):
            iface.memory_map = MemoryMap(addr_width=32, data_width=32)

    def test_set_wrong_map_addr_width(self):
        iface = wishbone.Interface(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has address width 30, which is not the same as the bus interface "
                r"effective address width 32 \(= 30 address bits \+ 2 granularity bits\)"):
            iface.memory_map = MemoryMap(addr_width=30, data_width=8)


class DecoderTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = wishbone.Decoder(addr_width=31, data_width=32, granularity=16)

    def test_add_align_to(self):
        sub_1 = wishbone.Interface(addr_width=15, data_width=32, granularity=16)
        sub_1.memory_map = MemoryMap(addr_width=16, data_width=16)
        sub_2 = wishbone.Interface(addr_width=15, data_width=32, granularity=16)
        sub_2.memory_map = MemoryMap(addr_width=16, data_width=16)
        self.assertEqual(self.dut.add(sub_1), (0x00000000, 0x00010000, 1))
        self.assertEqual(self.dut.align_to(18), 0x000040000)
        self.assertEqual(self.dut.align_to(alignment=18), 0x000040000)
        self.assertEqual(self.dut.add(sub_2), (0x00040000, 0x00050000, 1))

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Subordinate bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add(sub_bus="foo")

    def test_add_wrong_granularity(self):
        sub = wishbone.Interface(addr_width=15, data_width=32, granularity=32)
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has granularity 32, which is greater than "
                r"the decoder granularity 16"):
            self.dut.add(sub)

    def test_add_wrong_width_dense(self):
        sub = wishbone.Interface(addr_width=15, data_width=16, granularity=16)
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 16, which is not the same as decoder "
                r"data width 32 \(required for dense address translation\)"):
            self.dut.add(sub)

    def test_add_wrong_granularity_sparse(self):
        sub = wishbone.Interface(addr_width=15, data_width=64, granularity=16)
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 64, which is not the same as its "
                r"granularity 16 \(required for sparse address translation\)"):
            self.dut.add(sub, sparse=True)

    def test_add_wrong_optional_output(self):
        sub = wishbone.Interface(addr_width=15, data_width=32, granularity=16, features={"err"})
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has optional output 'err', but the decoder does "
                r"not have a corresponding input"):
            self.dut.add(sub)

    def test_add_wrong_out_of_bounds(self):
        sub = wishbone.Interface(addr_width=31, data_width=32, granularity=16)
        sub.memory_map = MemoryMap(addr_width=32, data_width=16)
        with self.assertRaisesRegex(ValueError,
            r"Address range 0x1\.\.0x100000001 out of bounds for memory map spanning "
            r"range 0x0\.\.0x100000000 \(32 address bits\)"):
            self.dut.add(sub, addr=1)


class DecoderSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                               features={"err", "rty", "stall", "lock", "cti", "bte"})
        sub_1 = wishbone.Interface(addr_width=14, data_width=32, granularity=8)
        sub_1.memory_map = MemoryMap(addr_width=16, data_width=8)
        dut.add(sub_1, addr=0x10000)
        sub_2 = wishbone.Interface(addr_width=14, data_width=32, granularity=8,
                                   features={"err", "rty", "stall", "lock", "cti", "bte"})
        sub_2.memory_map = MemoryMap(addr_width=16, data_width=8)
        dut.add(sub_2)

        async def testbench(ctx):
            ctx.set(dut.bus.adr, 0x10400 >> 2)
            ctx.set(dut.bus.cyc, 1)
            ctx.set(dut.bus.stb, 1)
            ctx.set(dut.bus.sel, 0b11)
            ctx.set(dut.bus.dat_w, 0x12345678)
            ctx.set(dut.bus.lock, 1)
            ctx.set(dut.bus.cti, wishbone.CycleType.INCR_BURST)
            ctx.set(dut.bus.bte, wishbone.BurstTypeExt.WRAP_4)
            ctx.set(sub_1.ack, 1)
            ctx.set(sub_1.dat_r, 0xabcdef01)
            ctx.set(sub_2.dat_r, 0x5678abcd)
            self.assertEqual(ctx.get(sub_1.adr), 0x400 >> 2)
            self.assertEqual(ctx.get(sub_1.cyc), 1)
            self.assertEqual(ctx.get(sub_2.cyc), 0)
            self.assertEqual(ctx.get(sub_1.stb), 1)
            self.assertEqual(ctx.get(sub_1.sel), 0b11)
            self.assertEqual(ctx.get(sub_1.dat_w), 0x12345678)
            self.assertEqual(ctx.get(dut.bus.ack), 1)
            self.assertEqual(ctx.get(dut.bus.err), 0)
            self.assertEqual(ctx.get(dut.bus.rty), 0)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0xabcdef01)

            ctx.set(dut.bus.adr, 0x20400 >> 2)
            ctx.set(sub_1.ack, 0)
            ctx.set(sub_2.err, 1)
            ctx.set(sub_2.rty, 1)
            ctx.set(sub_2.stall, 1)
            self.assertEqual(ctx.get(sub_2.adr), 0x400 >> 2)
            self.assertEqual(ctx.get(sub_1.cyc), 0)
            self.assertEqual(ctx.get(sub_2.cyc), 1)
            self.assertEqual(ctx.get(sub_1.stb), 1)
            self.assertEqual(ctx.get(sub_1.sel), 0b11)
            self.assertEqual(ctx.get(sub_1.dat_w), 0x12345678)
            self.assertEqual(ctx.get(sub_2.lock), 1)
            self.assertEqual(ctx.get(sub_2.cti), wishbone.CycleType.INCR_BURST.value)
            self.assertEqual(ctx.get(sub_2.bte), wishbone.BurstTypeExt.WRAP_4.value)
            self.assertEqual(ctx.get(dut.bus.ack), 0)
            self.assertEqual(ctx.get(dut.bus.err), 1)
            self.assertEqual(ctx.get(dut.bus.rty), 1)
            self.assertEqual(ctx.get(dut.bus.stall), 1)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x5678abcd)

        sim = Simulator(dut)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_addr_translate(self):
        class AddressLoopback(Elaboratable):
            def __init__(self, **kwargs):
                self.bus = wishbone.Interface(**kwargs)

            def elaborate(self, platform):
                m = Module()

                for index, sel_bit in enumerate(self.bus.sel):
                    with m.If(sel_bit):
                        segment = self.bus.dat_r.word_select(index, self.bus.granularity)
                        m.d.comb += segment.eq(self.bus.adr + index)

                return m

        dut = wishbone.Decoder(addr_width=20, data_width=32, granularity=16)
        loop_1 = AddressLoopback(addr_width=7, data_width=32, granularity=16)
        loop_1.bus.memory_map = MemoryMap(addr_width=8, data_width=16)
        self.assertEqual(dut.add(loop_1.bus, addr=0x10000),
                         (0x10000, 0x10100, 1))
        loop_2 = AddressLoopback(addr_width=6, data_width=32, granularity=8)
        loop_2.bus.memory_map = MemoryMap(addr_width=8, data_width=8, alignment=1)
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

        async def testbench(ctx):
            ctx.set(dut.bus.cyc, 1)
            ctx.set(dut.bus.adr, 0x10010 >> 1)

            ctx.set(dut.bus.sel, 0b11)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x00090008)

            ctx.set(dut.bus.sel, 0b01)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x00000008)

            ctx.set(dut.bus.sel, 0b10)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x00090000)

            ctx.set(dut.bus.adr, 0x20010 >> 1)

            ctx.set(dut.bus.sel, 0b11)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x13121110)

            ctx.set(dut.bus.sel, 0b01)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x00001110)

            ctx.set(dut.bus.sel, 0b10)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x13120000)

            ctx.set(dut.bus.adr, 0x30010 >> 1)

            ctx.set(dut.bus.sel, 0b11)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x0008)

            ctx.set(dut.bus.sel, 0b01)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x0008)

            ctx.set(dut.bus.sel, 0b10)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x0000)

            ctx.set(dut.bus.adr, 0x30012 >> 1)

            ctx.set(dut.bus.sel, 0b11)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x0009)

            ctx.set(dut.bus.adr, 0x40010 >> 1)

            ctx.set(dut.bus.sel, 0b11)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x08)

            ctx.set(dut.bus.sel, 0b01)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x08)

            ctx.set(dut.bus.sel, 0b10)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x00)

            ctx.set(dut.bus.adr, 0x40012 >> 1)

            ctx.set(dut.bus.sel, 0b11)
            self.assertEqual(ctx.get(dut.bus.dat_r), 0x09)

        m = Module()
        m.submodules.loop_1 = loop_1
        m.submodules.loop_2 = loop_2
        m.submodules.loop_3 = loop_3
        m.submodules.loop_4 = loop_4
        m.submodules.dut = dut

        sim = Simulator(m)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_coarse_granularity(self):
        dut = wishbone.Decoder(addr_width=3, data_width=32)
        sub = wishbone.Interface(addr_width=2, data_width=32)
        sub.memory_map = MemoryMap(addr_width=2, data_width=32)
        dut.add(sub)

        async def testbench(ctx):
            ctx.set(dut.bus.cyc, 1)
            ctx.set(dut.bus.adr, 0x0)
            self.assertEqual(ctx.get(sub.cyc), 1)
            ctx.set(dut.bus.adr, 0x4)
            self.assertEqual(ctx.get(sub.cyc), 0)

        sim = Simulator(dut)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


class ArbiterTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = wishbone.Arbiter(addr_width=31, data_width=32, granularity=16,
                                    features={"err"})

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Initiator bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add(intr_bus="foo")

    def test_add_wrong_addr_width(self):
        intr = wishbone.Interface(addr_width=15, data_width=32, granularity=16,
                                  features={"err"}, path=("intr",))
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has address width 15, which is not the same as arbiter "
                r"address width 31"):
            self.dut.add(intr)

    def test_add_wrong_granularity(self):
        intr = wishbone.Interface(addr_width=31, data_width=32, granularity=8,
                                  features={"err"}, path=("intr",))
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has granularity 8, which is lesser than "
                r"the arbiter granularity 16"):
            self.dut.add(intr)

    def test_add_wrong_data_width(self):
        intr = wishbone.Interface(addr_width=31, data_width=16, granularity=16,
                                  features={"err"}, path=("intr",))
        with self.assertRaisesRegex(ValueError,
                r"Initiator bus has data width 16, which is not the same as arbiter "
                r"data width 32"):
            self.dut.add(intr)

    def test_add_wrong_optional_output(self):
        intr = wishbone.Interface(addr_width=31, data_width=32, granularity=16, path=("intr",))
        with self.assertRaisesRegex(ValueError,
                r"Arbiter has optional output 'err', but the initiator bus does "
                r"not have a corresponding input"):
            self.dut.add(intr)


class ArbiterSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                               features={"err", "rty", "stall", "lock", "cti", "bte"})

        intr_1 = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                    features={"err", "rty"}, path=("intr_1",))
        dut.add(intr_1)
        intr_2 = wishbone.Interface(addr_width=30, data_width=32, granularity=16,
                                    features={"err", "rty", "stall", "lock", "cti",
                                              "bte"},
                                    path=("intr_2",))
        dut.add(intr_2)

        async def testbench(ctx):
            ctx.set(intr_1.adr, 0x7ffffffc >> 2)
            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_1.stb, 1)
            ctx.set(intr_1.sel, 0b1111)
            ctx.set(intr_1.we, 1)
            ctx.set(intr_1.dat_w, 0x12345678)
            ctx.set(dut.bus.dat_r, 0xabcdef01)
            ctx.set(dut.bus.ack, 1)
            ctx.set(dut.bus.err, 1)
            ctx.set(dut.bus.rty, 1)
            self.assertEqual(ctx.get(dut.bus.adr), 0x7ffffffc >> 2)
            self.assertEqual(ctx.get(dut.bus.cyc), 1)
            self.assertEqual(ctx.get(dut.bus.stb), 1)
            self.assertEqual(ctx.get(dut.bus.sel), 0b1111)
            self.assertEqual(ctx.get(dut.bus.we), 1)
            self.assertEqual(ctx.get(dut.bus.dat_w), 0x12345678)
            self.assertEqual(ctx.get(dut.bus.lock), 0)
            self.assertEqual(ctx.get(dut.bus.cti), wishbone.CycleType.CLASSIC.value)
            self.assertEqual(ctx.get(dut.bus.bte), wishbone.BurstTypeExt.LINEAR.value)
            self.assertEqual(ctx.get(intr_1.dat_r), 0xabcdef01)
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_1.err), 1)
            self.assertEqual(ctx.get(intr_1.rty), 1)

            ctx.set(intr_1.cyc, 0)
            ctx.set(intr_2.adr, 0xe0000000 >> 2)
            ctx.set(intr_2.cyc, 1)
            ctx.set(intr_2.stb, 1)
            ctx.set(intr_2.sel, 0b10)
            ctx.set(intr_2.we, 1)
            ctx.set(intr_2.dat_w, 0x43218765)
            ctx.set(intr_2.lock, 0)
            ctx.set(intr_2.cti, wishbone.CycleType.INCR_BURST)
            ctx.set(intr_2.bte, wishbone.BurstTypeExt.WRAP_4)
            await ctx.tick()

            ctx.set(dut.bus.stall, 0)
            self.assertEqual(ctx.get(dut.bus.adr), 0xe0000000 >> 2)
            self.assertEqual(ctx.get(dut.bus.cyc), 1)
            self.assertEqual(ctx.get(dut.bus.stb), 1)
            self.assertEqual(ctx.get(dut.bus.sel), 0b1100)
            self.assertEqual(ctx.get(dut.bus.we), 1)
            self.assertEqual(ctx.get(dut.bus.dat_w), 0x43218765)
            self.assertEqual(ctx.get(dut.bus.lock), 0)
            self.assertEqual(ctx.get(dut.bus.cti), wishbone.CycleType.INCR_BURST.value)
            self.assertEqual(ctx.get(dut.bus.bte), wishbone.BurstTypeExt.WRAP_4.value)
            self.assertEqual(ctx.get(intr_2.dat_r), 0xabcdef01)
            self.assertEqual(ctx.get(intr_2.ack), 1)
            self.assertEqual(ctx.get(intr_2.err), 1)
            self.assertEqual(ctx.get(intr_2.rty), 1)
            self.assertEqual(ctx.get(intr_2.stall), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_lock(self):
        dut = wishbone.Arbiter(addr_width=30, data_width=32, features={"lock"})
        sig = wishbone.Signature(addr_width=30, data_width=32, features={"lock"})
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
        dut.add(intr_2)

        async def testbench(ctx):
            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_1.lock, 1)
            ctx.set(intr_2.cyc, 1)
            ctx.set(dut.bus.ack, 1)
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_2.ack), 0)

            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_2.ack), 0)

            ctx.set(intr_1.lock, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 0)
            self.assertEqual(ctx.get(intr_2.ack), 1)

            ctx.set(intr_2.cyc, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_2.ack), 0)

            ctx.set(intr_1.stb, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_2.ack), 0)

            ctx.set(intr_1.stb, 0)
            ctx.set(intr_2.cyc, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 0)
            self.assertEqual(ctx.get(intr_2.ack), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_stall(self):
        dut = wishbone.Arbiter(addr_width=30, data_width=32, features={"stall"})
        sig = wishbone.Signature(addr_width=30, data_width=32, features={"stall"})
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
        dut.add(intr_2)

        async def testbench(ctx):
            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_2.cyc, 1)
            ctx.set(dut.bus.stall, 0)
            self.assertEqual(ctx.get(intr_1.stall), 0)
            self.assertEqual(ctx.get(intr_2.stall), 1)

            ctx.set(dut.bus.stall, 1)
            self.assertEqual(ctx.get(intr_1.stall), 1)
            self.assertEqual(ctx.get(intr_2.stall), 1)

        sim = Simulator(dut)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_stall_compat(self):
        dut = wishbone.Arbiter(addr_width=30, data_width=32)
        sig = wishbone.Signature(addr_width=30, data_width=32, features={"stall"})
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
        dut.add(intr_2)

        async def testbench(ctx):
            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_2.cyc, 1)
            self.assertEqual(ctx.get(intr_1.stall), 1)
            self.assertEqual(ctx.get(intr_2.stall), 1)

            ctx.set(dut.bus.ack, 1)
            self.assertEqual(ctx.get(intr_1.stall), 0)
            self.assertEqual(ctx.get(intr_2.stall), 1)

        sim = Simulator(dut)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_roundrobin(self):
        dut = wishbone.Arbiter(addr_width=30, data_width=32)
        sig = wishbone.Signature(addr_width=30, data_width=32)
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
        dut.add(intr_2)
        intr_3 = sig.create(path=("intr_3",))
        dut.add(intr_3)

        async def testbench(ctx):
            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_2.cyc, 0)
            ctx.set(intr_3.cyc, 1)
            ctx.set(dut.bus.ack, 1)
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_2.ack), 0)
            self.assertEqual(ctx.get(intr_3.ack), 0)

            ctx.set(intr_1.cyc, 0)
            ctx.set(intr_2.cyc, 0)
            ctx.set(intr_3.cyc, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 0)
            self.assertEqual(ctx.get(intr_2.ack), 0)
            self.assertEqual(ctx.get(intr_3.ack), 1)

            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_2.cyc, 1)
            ctx.set(intr_3.cyc, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 1)
            self.assertEqual(ctx.get(intr_2.ack), 0)
            self.assertEqual(ctx.get(intr_3.ack), 0)

            ctx.set(intr_1.cyc, 0)
            ctx.set(intr_2.cyc, 1)
            ctx.set(intr_3.cyc, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 0)
            self.assertEqual(ctx.get(intr_2.ack), 1)
            self.assertEqual(ctx.get(intr_3.ack), 0)

            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_2.cyc, 0)
            ctx.set(intr_3.cyc, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(intr_1.ack), 0)
            self.assertEqual(ctx.get(intr_2.ack), 0)
            self.assertEqual(ctx.get(intr_3.ack), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
