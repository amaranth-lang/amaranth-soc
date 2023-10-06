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
        iface = sig.create(path=("foo", "bar"))
        self.assertIsInstance(iface, wishbone.Interface)
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 16)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.cyc.name, "foo__bar__cyc")
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
                r"Address width must be a positive integer, not 0"):
            wishbone.Signature(addr_width=0, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Address width must be a positive integer, not 0"):
            wishbone.Signature.check_parameters(addr_width=0, data_width=8, granularity=8,
                                                features=())

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be one of 8, 16, 32, 64, not 7"):
            wishbone.Signature(addr_width=1, data_width=7)
        with self.assertRaisesRegex(ValueError,
                r"Data width must be one of 8, 16, 32, 64, not 7"):
            wishbone.Signature.check_parameters(addr_width=1, data_width=7, granularity=7,
                                                features=())

    def test_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity must be one of 8, 16, 32, 64, not 7"):
            wishbone.Signature(addr_width=1, data_width=32, granularity=7)
        with self.assertRaisesRegex(ValueError,
                r"Granularity must be one of 8, 16, 32, 64, not 7"):
            wishbone.Signature.check_parameters(addr_width=1, data_width=32, granularity=7,
                                                features=())

    def test_wrong_granularity_wide(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity 32 may not be greater than data width 8"):
            wishbone.Signature(addr_width=1, data_width=8, granularity=32)
        with self.assertRaisesRegex(ValueError,
                r"Granularity 32 may not be greater than data width 8"):
            wishbone.Signature.check_parameters(addr_width=1, data_width=8, granularity=32,
                                                features=())

    def test_wrong_features(self):
        with self.assertRaisesRegex(ValueError, r"'foo' is not a valid Feature"):
            wishbone.Signature(addr_width=1, data_width=8, features={"foo"})
        with self.assertRaisesRegex(ValueError, r"'foo' is not a valid Feature"):
            wishbone.Signature.check_parameters(addr_width=1, data_width=8, granularity=8,
                                                features={"foo"})

    def test_set_map(self):
        sig = wishbone.Signature(addr_width=15, data_width=16, granularity=8)
        memory_map = MemoryMap(addr_width=16, data_width=8)
        sig.memory_map = memory_map
        self.assertIs(sig.memory_map, memory_map)

    def test_get_map_none(self):
        sig = wishbone.Signature(addr_width=8, data_width=8)
        with self.assertRaisesRegex(AttributeError,
                r"wishbone.Signature\(.*\) does not have a memory map"):
            sig.memory_map

    def test_set_map_frozen(self):
        sig = wishbone.Signature(addr_width=8, data_width=8)
        sig.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Signature has been frozen\. Cannot set its memory map"):
            sig.memory_map = MemoryMap(addr_width=8, data_width=8)

    def test_set_wrong_map(self):
        sig = wishbone.Signature(addr_width=8, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            sig.memory_map = "foo"

    def test_set_wrong_map_data_width(self):
        sig = wishbone.Signature(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has data width 32, which is not the same as bus "
                r"interface granularity 8"):
            sig.memory_map = MemoryMap(addr_width=32, data_width=32)

    def test_set_wrong_map_addr_width(self):
        sig = wishbone.Signature(addr_width=30, data_width=32, granularity=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has address width 30, which is not the same as the bus interface "
                r"effective address width 32 \(= 30 address bits \+ 2 granularity bits\)"):
            sig.memory_map = MemoryMap(addr_width=30, data_width=8)


class InterfaceTestCase(unittest.TestCase):
    def test_simple(self):
        iface = wishbone.Interface(addr_width=32, data_width=8, features={"err"},
                                   path=("foo", "bar"))
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.features, {wishbone.Feature.ERR})
        self.assertEqual(iface.cyc.name, "foo__bar__cyc")

    def test_map(self):
        memory_map = MemoryMap(addr_width=32, data_width=8)
        iface = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                   memory_map=memory_map, path=("iface",))
        self.assertIs(iface.memory_map, memory_map)

    def test_get_map_none(self):
        iface = wishbone.Interface(addr_width=1, data_width=8, path=("iface",))
        with self.assertRaisesRegex(AttributeError,
                r"wishbone.Signature\(.*\) does not have a memory map"):
            iface.memory_map

    def test_wrong_map(self):
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            wishbone.Interface(addr_width=1, data_width=8, memory_map="foo")

    def test_wrong_map_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Memory map has data width 32, which is not the same as bus "
                r"interface granularity 8"):
            wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                               memory_map=MemoryMap(addr_width=32, data_width=32))

    def test_wrong_map_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Memory map has address width 30, which is not the same as the bus interface "
                r"effective address width 32 \(= 30 address bits \+ 2 granularity bits\)"):
            wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                               memory_map=MemoryMap(addr_width=30, data_width=8))


class DecoderTestCase(unittest.TestCase):
    def setUp(self):
        self.dut = wishbone.Decoder(addr_width=31, data_width=32, granularity=16)

    def test_add_align_to(self):
        sig_1 = wishbone.Signature(addr_width=15, data_width=32, granularity=16)
        sig_1.memory_map = MemoryMap(addr_width=16, data_width=16)
        sig_2 = wishbone.Signature(addr_width=15, data_width=32, granularity=16)
        sig_2.memory_map = MemoryMap(addr_width=16, data_width=16)
        sub_1 = sig_1.create(path=("sub_1"))
        sub_2 = sig_2.create(path=("sub_2"))
        self.assertEqual(self.dut.add(sub_1), (0x00000000, 0x00010000, 1))
        self.assertEqual(self.dut.align_to(18), 0x000040000)
        self.assertEqual(self.dut.align_to(alignment=18), 0x000040000)
        self.assertEqual(self.dut.add(sub_2), (0x00040000, 0x00050000, 1))

    def test_add_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Subordinate bus must be an instance of wishbone\.Interface, not 'foo'"):
            self.dut.add(sub_bus="foo")

    def test_add_wrong_granularity(self):
        sub = wishbone.Interface(addr_width=15, data_width=32, granularity=32, path=("sub",))
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has granularity 32, which is greater than "
                r"the decoder granularity 16"):
            self.dut.add(sub)

    def test_add_wrong_width_dense(self):
        sub = wishbone.Interface(addr_width=15, data_width=16, granularity=16, path=("sub",))
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 16, which is not the same as decoder "
                r"data width 32 \(required for dense address translation\)"):
            self.dut.add(sub)

    def test_add_wrong_granularity_sparse(self):
        sub = wishbone.Interface(addr_width=15, data_width=64, granularity=16, path=("sub",))
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has data width 64, which is not the same as its "
                r"granularity 16 \(required for sparse address translation\)"):
            self.dut.add(sub, sparse=True)

    def test_add_wrong_optional_output(self):
        sub = wishbone.Interface(addr_width=15, data_width=32, granularity=16, features={"err"},
                                 path=("sub",))
        with self.assertRaisesRegex(ValueError,
                r"Subordinate bus has optional output 'err', but the decoder does "
                r"not have a corresponding input"):
            self.dut.add(sub)

    def test_add_wrong_out_of_bounds(self):
        sub = wishbone.Interface(addr_width=31, data_width=32, granularity=16,
                                 memory_map=MemoryMap(addr_width=32, data_width=16),
                                 path=("sub",))
        with self.assertRaisesRegex(ValueError,
            r"Address range 0x1\.\.0x100000001 out of bounds for memory map spanning "
            r"range 0x0\.\.0x100000000 \(32 address bits\)"):
            self.dut.add(sub, addr=1)


class DecoderSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                               features={"err", "rty", "stall", "lock", "cti", "bte"})
        sub_1 = wishbone.Interface(addr_width=14, data_width=32, granularity=8,
                                   memory_map=MemoryMap(addr_width=16, data_width=8),
                                   path=("sub_1",))
        dut.add(sub_1, addr=0x10000)
        sub_2 = wishbone.Interface(addr_width=14, data_width=32, granularity=8,
                                   features={"err", "rty", "stall", "lock", "cti", "bte"},
                                   memory_map=MemoryMap(addr_width=16, data_width=8),
                                   path=("sub_2",))
        dut.add(sub_2)

        def sim_test():
            yield dut.bus.adr.eq(0x10400 >> 2)
            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield dut.bus.sel.eq(0b11)
            yield dut.bus.dat_w.eq(0x12345678)
            yield dut.bus.lock.eq(1)
            yield dut.bus.cti.eq(wishbone.CycleType.INCR_BURST)
            yield dut.bus.bte.eq(wishbone.BurstTypeExt.WRAP_4)
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
            self.assertEqual((yield sub_2.cti), wishbone.CycleType.INCR_BURST.value)
            self.assertEqual((yield sub_2.bte), wishbone.BurstTypeExt.WRAP_4.value)
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
                self.bus = wishbone.Interface(path=("bus",), **kwargs)

            def elaborate(self, platform):
                m = Module()

                for index, sel_bit in enumerate(self.bus.sel):
                    with m.If(sel_bit):
                        segment = self.bus.dat_r.word_select(index, self.bus.granularity)
                        m.d.comb += segment.eq(self.bus.adr + index)

                return m

        dut = wishbone.Decoder(addr_width=20, data_width=32, granularity=16)
        loop_1 = AddressLoopback(addr_width=7, data_width=32, granularity=16,
                                 memory_map=MemoryMap(addr_width=8, data_width=16))
        self.assertEqual(dut.add(loop_1.bus, addr=0x10000),
                         (0x10000, 0x10100, 1))
        loop_2 = AddressLoopback(addr_width=6, data_width=32, granularity=8,
                                 memory_map=MemoryMap(addr_width=8, data_width=8))
        self.assertEqual(dut.add(loop_2.bus, addr=0x20000),
                         (0x20000, 0x20080, 2))
        loop_3 = AddressLoopback(addr_width=8, data_width=16, granularity=16,
                                 memory_map=MemoryMap(addr_width=8, data_width=16))
        self.assertEqual(dut.add(loop_3.bus, addr=0x30000, sparse=True),
                         (0x30000, 0x30100, 1))
        loop_4 = AddressLoopback(addr_width=8, data_width=8,  granularity=8,
                                 memory_map=MemoryMap(addr_width=8, data_width=8))
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
        dut = wishbone.Decoder(addr_width=3, data_width=32)
        sub = wishbone.Interface(addr_width=2, data_width=32,
                                 memory_map=MemoryMap(addr_width=2, data_width=32),
                                 path=("sub",))
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
            self.assertEqual((yield dut.bus.cti), wishbone.CycleType.CLASSIC.value)
            self.assertEqual((yield dut.bus.bte), wishbone.BurstTypeExt.LINEAR.value)
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
            yield intr_2.cti.eq(wishbone.CycleType.INCR_BURST)
            yield intr_2.bte.eq(wishbone.BurstTypeExt.WRAP_4)
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
            self.assertEqual((yield dut.bus.cti), wishbone.CycleType.INCR_BURST.value)
            self.assertEqual((yield dut.bus.bte), wishbone.BurstTypeExt.WRAP_4.value)
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
        dut = wishbone.Arbiter(addr_width=30, data_width=32, features={"lock"})
        sig = wishbone.Signature(addr_width=30, data_width=32, features={"lock"})
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
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
        dut = wishbone.Arbiter(addr_width=30, data_width=32, features={"stall"})
        sig = wishbone.Signature(addr_width=30, data_width=32, features={"stall"})
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
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
        dut = wishbone.Arbiter(addr_width=30, data_width=32)
        sig = wishbone.Signature(addr_width=30, data_width=32, features={"stall"})
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
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
        dut = wishbone.Arbiter(addr_width=30, data_width=32)
        sig = wishbone.Signature(addr_width=30, data_width=32)
        intr_1 = sig.create(path=("intr_1",))
        dut.add(intr_1)
        intr_2 = sig.create(path=("intr_2",))
        dut.add(intr_2)
        intr_3 = sig.create(path=("intr_3",))
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
