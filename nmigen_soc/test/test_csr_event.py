# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.back.pysim import *

from ..csr import *
from .. import event


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd(vcd_file=open("test.vcd", "w")):
        sim.run()


class EventMonitorTestCase(unittest.TestCase):
    def test_params(self):
        monitor = EventMonitor(data_width=16, alignment=4, trigger="rise")
        self.assertEqual(monitor.bus.data_width, 16)
        self.assertEqual(monitor.bus.memory_map.alignment, 4)
        self.assertEqual(monitor.src.trigger, event.Source.Trigger.RISE)

    def test_trigger_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Invalid trigger mode 'foo'; must be one of level, rise, fall"):
            EventMonitor(data_width=8, trigger="foo")

    def test_add(self):
        monitor = EventMonitor(data_width=8)
        sub = event.Source()
        monitor.add(sub)
        self.assertEqual(monitor.src.event_map.size, 1)
        self.assertEqual(monitor.src.event_map.index(sub), 0)

    def test_freeze(self):
        monitor = EventMonitor(data_width=8)
        monitor.freeze()
        sub = event.Source()
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen. Cannot add source."):
            monitor.add(sub)

    def test_src_freeze(self):
        monitor = EventMonitor(data_width=8)
        monitor.src
        sub = event.Source()
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen. Cannot add source."):
            monitor.add(sub)

    def test_bus_freeze(self):
        monitor = EventMonitor(data_width=8)
        monitor.bus
        sub = event.Source()
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen. Cannot add source."):
            monitor.add(sub)

    def test_csr_regs(self):
        monitor = EventMonitor(data_width=8)
        sub_0 = event.Source()
        sub_1 = event.Source()
        monitor.add(sub_0)
        monitor.add(sub_1)
        resources = list(monitor.bus.memory_map.resources())
        self.assertEqual(len(resources), 2)
        enable,  enable_range  = resources[0]
        pending, pending_range = resources[1]
        self.assertEqual(
            (enable.width, enable.access, enable_range),
            (2, Element.Access.RW, (0, 1))
        )
        self.assertEqual(
            (pending.width, pending.access, pending_range),
            (2, Element.Access.RW, (1, 2))
        )

    def test_freeze_idempotent(self):
        monitor = EventMonitor(data_width=8)
        src = monitor.src
        bus = monitor.bus
        monitor.freeze()
        self.assertIs(src, monitor.src)
        self.assertIs(bus, monitor.bus)


class EventMonitorSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        dut = EventMonitor(data_width=8)
        sub = event.Source()
        dut.add(sub)

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
