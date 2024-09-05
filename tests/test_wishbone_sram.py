# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.sim import *

from amaranth_soc import wishbone
from amaranth_soc.wishbone.sram import WishboneSRAM


class WishboneSRAMTestCase(unittest.TestCase):
    def test_init(self):
        # default granularity, writable, no initial values
        dut_1 = WishboneSRAM(size=1024, data_width=32)
        self.assertEqual(dut_1.size, 1024)
        self.assertEqual(dut_1.writable, True)
        self.assertEqual(list(dut_1.init), [0 for _ in range(1024)])
        self.assertEqual(dut_1.wb_bus.addr_width, 10)
        self.assertEqual(dut_1.wb_bus.data_width, 32)
        self.assertEqual(dut_1.wb_bus.granularity, 32)
        self.assertEqual(dut_1.wb_bus.features, frozenset())
        self.assertEqual(dut_1.wb_bus.memory_map.addr_width, 10)
        self.assertEqual(dut_1.wb_bus.memory_map.data_width, 32)
        self.assertEqual(dut_1.wb_bus.memory_map.alignment, 0)
        self.assertEqual(list(dut_1.wb_bus.memory_map.resources()),
                         [(dut_1._mem, ("mem",), (0, 1024))])
        # custom granularity, read-only, with initial values
        dut_2 = WishboneSRAM(size=4, data_width=16, granularity=8, writable=False,
                              init=(0xbbaa, 0xddcc))
        self.assertEqual(dut_2.size, 4)
        self.assertEqual(dut_2.writable, False)
        self.assertEqual(list(dut_2.init), [0xbbaa, 0xddcc])
        self.assertEqual(dut_2.wb_bus.addr_width, 1)
        self.assertEqual(dut_2.wb_bus.data_width, 16)
        self.assertEqual(dut_2.wb_bus.granularity, 8)
        self.assertEqual(dut_2.wb_bus.features, frozenset())
        self.assertEqual(dut_2.wb_bus.memory_map.addr_width, 2)
        self.assertEqual(dut_2.wb_bus.memory_map.data_width, 8)
        self.assertEqual(dut_2.wb_bus.memory_map.alignment, 0)
        self.assertEqual(list(dut_2.wb_bus.memory_map.resources()),
                         [(dut_2._mem, ("mem",), (0, 4))])

    def test_memory_data_init_set(self):
        dut = WishboneSRAM(size=4, data_width=16, granularity=8)
        self.assertEqual(list(dut.init), [0x0000, 0x0000])
        dut.init = [0xbbaa, 0xddcc]
        self.assertEqual(list(dut._mem_data.init), [0xbbaa, 0xddcc])

    def test_init_wrong_size(self):
        with self.assertRaisesRegex(TypeError, r"Size must be an integer power of two, not 1.0"):
            WishboneSRAM(size=1.0, data_width=32)
        with self.assertRaisesRegex(TypeError, r"Size must be an integer power of two, not 3"):
            WishboneSRAM(size=3, data_width=32)

    def test_init_wrong_data_width(self):
        with self.assertRaisesRegex(TypeError, r"Data width must be 8, 16, 32 or 64, not 'foo'"):
            WishboneSRAM(size=1024, data_width="foo")
        with self.assertRaisesRegex(TypeError, r"Data width must be 8, 16, 32 or 64, not 128"):
            WishboneSRAM(size=1024, data_width=128)

    def test_init_wrong_granularity(self):
        with self.assertRaisesRegex(TypeError, r"Granularity must be 8, 16, 32 or 64, not 'foo'"):
            WishboneSRAM(size=1024, data_width=32, granularity="foo")
        with self.assertRaisesRegex(TypeError, r"Granularity must be 8, 16, 32 or 64, not 128"):
            WishboneSRAM(size=1024, data_width=32, granularity=128)

    def test_init_size_smaller_than_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"The product of size 2 and granularity 8 must be greater than or equal to data "
                r"width 32, not 16"):
            WishboneSRAM(size=2, data_width=32, granularity=8)

    def test_sim_writable(self):
        dut = WishboneSRAM(size=128, data_width=32, granularity=8, writable=True, init=range(32))

        async def testbench(ctx):
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i)

            await ctx.tick()

            # - left shift all values by 24 bits:

            for i in range(32):
                ctx.set(dut.wb_bus.cyc, 1)
                ctx.set(dut.wb_bus.stb, 1)
                ctx.set(dut.wb_bus.adr, i)
                ctx.set(dut.wb_bus.sel, 0b1001)
                ctx.set(dut.wb_bus.we, 1)
                ctx.set(dut.wb_bus.dat_w, (i << 24) | 0x00ffff00)
                await ctx.tick()
                self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
                await ctx.tick()
                self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
                ctx.set(dut.wb_bus.cyc, 0)
                ctx.set(dut.wb_bus.stb, 0)
                await ctx.tick()

            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i << 24)

            await ctx.tick()

            # - right shift all values by 24 bits:

            ctx.set(dut.wb_bus.cyc, 1)
            ctx.set(dut.wb_bus.stb, 1)

            for i in range(32):
                ctx.set(dut.wb_bus.adr, i)
                ctx.set(dut.wb_bus.sel, 0b1001)
                ctx.set(dut.wb_bus.we, 1)
                ctx.set(dut.wb_bus.dat_w, i | 0x00ffff00)
                await ctx.tick()
                self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
                await ctx.tick()
                self.assertEqual(ctx.get(dut.wb_bus.ack), 0)

            ctx.set(dut.wb_bus.cyc, 0)
            ctx.set(dut.wb_bus.stb, 0)

            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_sim_readonly(self):
        dut = WishboneSRAM(size=128, data_width=32, granularity=8, writable=False, init=range(32))

        async def testbench(ctx):
            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i)

            for i in range(32):
                ctx.set(dut.wb_bus.cyc, 1)
                ctx.set(dut.wb_bus.stb, 1)
                ctx.set(dut.wb_bus.adr, i)
                ctx.set(dut.wb_bus.sel, 0xf)
                ctx.set(dut.wb_bus.we, 1)
                ctx.set(dut.wb_bus.dat_w, 0xffffffff)
                await ctx.tick().until(dut.wb_bus.ack)
                ctx.set(dut.wb_bus.cyc, 0)
                ctx.set(dut.wb_bus.stb, 0)
                await ctx.tick()

            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
