# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.sim import *

from amaranth_soc.csr import *
from amaranth_soc import event


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
        resources = list(monitor.bus.memory_map.all_resources())
        self.assertEqual(len(resources), 2)
        enable,   enable_range = resources[0].resource, (resources[0].start, resources[0].end)
        pending, pending_range = resources[1].resource, (resources[1].start, resources[1].end)
        self.assertEqual(
            (enable.element.width, enable.element.access, enable_range),
            (2, Element.Access.RW, (0, 1))
        )
        self.assertEqual(
            (pending.element.width, pending.element.access, pending_range),
            (2, Element.Access.RW, (1, 2))
        )


class EventMonitorSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        sub = event.Source()
        event_map = event.EventMap()
        event_map.add(sub)
        dut = EventMonitor(event_map, data_width=8)

        addr_enable  = 0x0
        addr_pending = 0x1

        async def testbench(ctx):
            ctx.set(sub.i, 1)
            self.assertEqual(ctx.get(sub.trg), 1)
            self.assertEqual(ctx.get(dut.src.i), 0)

            ctx.set(dut.bus.addr, addr_enable)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0b0)
            ctx.set(dut.bus.r_stb, 0)

            ctx.set(dut.bus.addr, addr_enable)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b1)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.src.i), 1)

            ctx.set(sub.i, 0)
            self.assertEqual(ctx.get(sub.trg), 0)

            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0b1)
            ctx.set(dut.bus.r_stb, 0)

            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b1)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()

            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), 0b0)
            ctx.set(dut.bus.r_stb, 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


