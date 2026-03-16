# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.back.pysim import *

from .. import sram


class WishboneBridgeTestCase(unittest.TestCase):
    def test_wrong_sram_buses(self):
        with self.assertRaisesRegex(
            ValueError,
            r"SRAM buses has to be an iterable of sram.Interface, not 'foo'",
        ):
            sram.WishboneBridge("foo")
        with self.assertRaisesRegex(
            ValueError,
            r"SRAM buses has to be an iterable of sram.Interface, not 'foo'",
        ):
            sram.WishboneBridge(sram_buses="foo")

    def test_wbbus_single(self):
        iface = sram.Interface(addr_width=10, data_width=8)
        bridge = sram.WishboneBridge(iface)
        self.assertEqual(bridge.wb_bus.addr_width, 10)
        self.assertEqual(bridge.wb_bus.data_width, 8)
        self.assertEqual(bridge.wb_bus.granularity, 8)
        self.assertFalse(hasattr(bridge.wb_bus, "stall"))

    def test_wbbus_multi(self):
        ifaces = [sram.Interface(addr_width=10, data_width=8) for _ in range(4)]
        bridge = sram.WishboneBridge(ifaces)
        self.assertEqual(bridge.wb_bus.addr_width, 10)
        self.assertEqual(bridge.wb_bus.data_width, 32)
        self.assertEqual(bridge.wb_bus.granularity, 8)
        self.assertFalse(hasattr(bridge.wb_bus, "stall"))
    
    def test_readwrite_single_nowait(self):
        iface = sram.Interface(addr_width=10, data_width=8)
        dut = sram.WishboneBridge(iface)

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.stb.eq(0)
            yield dut.wb_bus.sel.eq(0b1)
            yield
            self.assertFalse((yield iface.ce), 0)

            yield dut.wb_bus.we.eq(1)
            yield
            # we is only asserted when in Wishbone cycle
            self.assertEqual((yield iface.we), 0)

            yield dut.wb_bus.adr.eq(1)
            yield dut.wb_bus.dat_w.eq(0x55)
            yield dut.wb_bus.stb.eq(1)
            yield
            self.assertEqual((yield iface.we), 1)
            self.assertEqual((yield iface.a), 1)
            self.assertEqual((yield iface.d_w), 0x55)
            self.assertEqual((yield iface.ce), 1)
            self.assertEqual((yield dut.wb_bus.ack), 1)

            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)
            self.assertEqual((yield iface.we), 0)
            self.assertEqual((yield iface.ce), 0)

            yield dut.wb_bus.we.eq(0)
            yield dut.wb_bus.stb.eq(1)
            yield iface.d_r.eq(0x55)
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x55)
    
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_readwrite_multi_wait1(self):
        ifaces = [sram.Interface(addr_width=10, data_width=8) for _ in range(4)]
        a = ifaces[0].a
        ce = Cat(iface.ce for iface in ifaces)
        we = Cat(iface.we for iface in ifaces)
        d_w = Cat(iface.d_w for iface in ifaces)
        d_r = Cat(iface.d_r for iface in ifaces)

        dut = sram.WishboneBridge(ifaces, wait_states=Const(1, 1))

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.stb.eq(0)
            yield dut.wb_bus.sel.eq(0b1100)
            yield
            for iface in ifaces:
                self.assertFalse((yield iface.ce), 0)

            yield dut.wb_bus.we.eq(1)
            yield
            # we is only asserted when in Wishbone cycle
            self.assertEqual((yield we), 0b0000)

            yield dut.wb_bus.adr.eq(1)
            yield dut.wb_bus.dat_w.eq(0xAA55AA55)
            yield dut.wb_bus.stb.eq(1)
            yield
            self.assertEqual((yield we), 0b1100)
            self.assertEqual((yield a), 1)
            self.assertEqual((yield d_w), 0xAA55AA55)
            self.assertEqual((yield ce), 0b1100)
            self.assertEqual((yield dut.wb_bus.ack), 0)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)

            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield dut.wb_bus.ack), 0)
            self.assertEqual((yield we), 0b0000)
            self.assertEqual((yield ce), 0b0000)

            yield dut.wb_bus.we.eq(0)
            yield dut.wb_bus.stb.eq(1)
            yield d_r.eq(0xAA550000)
            yield
            self.assertEqual((yield dut.wb_bus.dat_r), 0xAA550000)
            self.assertEqual((yield dut.wb_bus.ack), 0)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.dat_r), 0xAA550000)
            self.assertEqual((yield dut.wb_bus.ack), 1)
    
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()
