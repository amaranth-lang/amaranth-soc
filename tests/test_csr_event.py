# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.sim import *

from amaranth_soc.csr import *
from amaranth_soc import event


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd(vcd_file=open("test.vcd", "w")):
        sim.run()


class EventMonitorTestCase(unittest.TestCase):
    def test_params(self):
        event_map = event.EventMap()
        monitor = EventMonitor(event_map, trigger="rise", data_width=16, alignment=4)
        self.assertEqual(monitor.src.trigger, event.Source.Trigger.RISE)
        self.assertEqual(monitor.bus.data_width, 16)
        self.assertEqual(monitor.bus.memory_map.alignment, 4)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive integer, not 'foo'"):
            EventMonitor(event.EventMap(), data_width='foo')
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive integer, not 0"):
            EventMonitor(event.EventMap(), data_width=0)

    def test_wrong_alignment(self):
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not 'foo'"):
            EventMonitor(event.EventMap(), data_width=8, alignment="foo")
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not -1"):
            EventMonitor(event.EventMap(), data_width=8, alignment=-1)

    def test_wrong_trigger(self):
        with self.assertRaisesRegex(ValueError,
                r"'foo' is not a valid Source.Trigger"):
            EventMonitor(event.EventMap(), data_width=8, trigger="foo")

    def test_csr_regs(self):
        sub_0 = event.Source(path=("sub_0",))
        sub_1 = event.Source(path=("sub_1",))
        event_map = event.EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        monitor = EventMonitor(event_map, data_width=8)
        resources = list(monitor.bus.memory_map.resources())
        self.assertEqual(len(resources), 2)
        enable,  enable_name,  enable_range  = resources[0]
        pending, pending_name, pending_range = resources[1]
        self.assertEqual(
            (enable.width, enable.access, enable_range),
            (2, Element.Access.RW, (0, 1))
        )
        self.assertEqual(
            (pending.width, pending.access, pending_range),
            (2, Element.Access.RW, (1, 2))
        )


class EventMonitorSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        sub = event.Source(path=("sub",))
        event_map = event.EventMap()
        event_map.add(sub)
        dut = EventMonitor(event_map, data_width=8)

        addr_enable  = 0x0
        addr_pending = 0x1

        def process():
            yield sub.i.eq(1)
            yield Delay()
            self.assertEqual((yield sub.trg), 1)
            self.assertEqual((yield dut.src.i), 0)

            yield dut.bus.addr.eq(addr_enable)
            yield dut.bus.r_stb.eq(1)
            yield
            yield dut.bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.bus.r_data), 0b0)
            yield

            yield dut.bus.addr.eq(addr_enable)
            yield dut.bus.w_stb.eq(1)
            yield dut.bus.w_data.eq(0b1)
            yield
            yield dut.bus.w_stb.eq(0)
            yield; yield Delay()

            self.assertEqual((yield dut.src.i), 1)
            yield sub.i.eq(0)
            yield Delay()
            self.assertEqual((yield sub.trg), 0)

            yield dut.bus.addr.eq(addr_pending)
            yield dut.bus.r_stb.eq(1)
            yield
            yield dut.bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.bus.r_data), 0b1)
            yield

            yield dut.bus.addr.eq(addr_pending)
            yield dut.bus.w_stb.eq(1)
            yield dut.bus.w_data.eq(0b1)
            yield
            yield dut.bus.w_stb.eq(0)
            yield

            yield dut.bus.addr.eq(addr_pending)
            yield dut.bus.r_stb.eq(1)
            yield
            yield dut.bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.bus.r_data), 0b0)

        simulation_test(dut, process)
