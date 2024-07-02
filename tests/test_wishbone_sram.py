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
        self.assertEqual(dut_1.wb_bus.features,
                         {wishbone.Feature.CTI, wishbone.Feature.BTE})
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
        self.assertEqual(dut_2.wb_bus.features,
                         {wishbone.Feature.CTI, wishbone.Feature.BTE})
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

        async def wb_cycle(ctx, *, adr, sel, we, dat_w, cti, bte=0, assert_dat_r=None):
            ctx.set(dut.wb_bus.cyc, 1)
            ctx.set(dut.wb_bus.stb, 1)
            ctx.set(dut.wb_bus.adr, adr)
            ctx.set(dut.wb_bus.sel, sel)
            ctx.set(dut.wb_bus.we, we)
            ctx.set(dut.wb_bus.dat_w, dat_w)
            ctx.set(dut.wb_bus.cti, cti)
            ctx.set(dut.wb_bus.bte, bte)

            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            if assert_dat_r is not None:
                self.assertEqual(ctx.get(dut.wb_bus.dat_r), assert_dat_r)

            ctx.set(dut.wb_bus.cyc, 0)
            ctx.set(dut.wb_bus.stb, 0)

        async def testbench(ctx):
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i)

            # cti = CLASSIC =======================================================================

            # - left shift all values by 24 bits:
            for i in range(32):
                await wb_cycle(ctx, cti=wishbone.CycleType.CLASSIC,
                               adr=i, sel=0b1001, we=1, dat_w=(i << 24) | 0x00ffff00,
                               assert_dat_r=i)
                await ctx.tick()
                self.assertEqual(ctx.get(dut.wb_bus.ack), 0)

            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i << 24)

            # cti = INCR_BURST, bte = LINEAR ======================================================

            # - right shift all values by 24 bits:
            for i in range(32):
                cti = wishbone.CycleType.END_OF_BURST if i == 31 else wishbone.CycleType.INCR_BURST
                await wb_cycle(ctx, cti=cti, bte=wishbone.BurstTypeExt.LINEAR,
                               adr=i, sel=0b1001, we=1, dat_w=i | 0x00ffff00,
                               assert_dat_r=i << 24)

            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            for i in range(32):
                self.assertEqual(ctx.get(dut._mem_data[i]), i)

            # cti = INCR_BURST, bte = WRAP_4 ======================================================

            # - increment values at addresses 0..15:
            for i in (1,2,3,0, 5,6,7,4, 9,10,11,8, 13,14,15,12):
                cti = wishbone.CycleType.END_OF_BURST if i == 12 else wishbone.CycleType.INCR_BURST
                await wb_cycle(ctx, cti=cti, bte=wishbone.BurstTypeExt.WRAP_4,
                               adr=i, sel=0b0001, we=1, dat_w=i + 1,
                               assert_dat_r=i)

            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            for i in range(16):
                self.assertEqual(ctx.get(dut._mem_data[i]), i + 1)

            # cti = INCR_BURST, bte = WRAP_8 ======================================================

            # - increment values at addresses 0..15:
            for i in (1,2,3,4,5,6,7,0, 9,10,11,12,13,14,15,8):
                cti = wishbone.CycleType.END_OF_BURST if i == 8 else wishbone.CycleType.INCR_BURST
                await wb_cycle(ctx, cti=cti, bte=wishbone.BurstTypeExt.WRAP_8,
                               adr=i, sel=0b0001, we=1, dat_w=i + 2,
                               assert_dat_r=i + 1)

            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            for i in range(16):
                self.assertEqual(ctx.get(dut._mem_data[i]), i + 2)

            # cti = INCR_BURST, bte = WRAP_16 =====================================================

            # - increment values at addresses 0..15:
            for i in (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,0):
                cti = wishbone.CycleType.END_OF_BURST if i == 0 else wishbone.CycleType.INCR_BURST
                await wb_cycle(ctx, cti=cti, bte=wishbone.BurstTypeExt.WRAP_16,
                               adr=i, sel=0b0001, we=1, dat_w=i + 3,
                               assert_dat_r=i + 2)

            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            for i in range(16):
                self.assertEqual(ctx.get(dut._mem_data[i]), i + 3)

            # cti = CONST_BURST ===================================================================

            # - increment value at address 31, 16 times in a row:
            for i in range(16):
                cti = wishbone.CycleType.END_OF_BURST if i == 15 else wishbone.CycleType.CONST_BURST
                await wb_cycle(ctx, cti=cti, adr=31, sel=0b0001, we=1, dat_w=31 + i + 1,
                               assert_dat_r=31 + i)

            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(dut._mem_data[31]), 31 + 16)

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
