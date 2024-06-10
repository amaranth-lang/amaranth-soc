# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.sim import *

from amaranth_soc import gpio


class PeripheralTestCase(unittest.TestCase):
    def test_init(self):
        dut_1 = gpio.Peripheral(pin_count=4, addr_width=2, data_width=8)
        self.assertEqual(dut_1.pin_count, 4)
        self.assertEqual(dut_1.input_stages, 2)
        self.assertEqual(dut_1.bus.addr_width, 2)
        self.assertEqual(dut_1.bus.data_width, 8)
        dut_2 = gpio.Peripheral(pin_count=1, addr_width=8, data_width=16, input_stages=3)
        self.assertEqual(dut_2.pin_count, 1)
        self.assertEqual(dut_2.input_stages, 3)
        self.assertEqual(dut_2.bus.addr_width, 8)
        self.assertEqual(dut_2.bus.data_width, 16)

    def test_init_wrong_pin_count(self):
        with self.assertRaisesRegex(TypeError,
                r"Pin count must be a positive integer, not 'foo'"):
            gpio.Peripheral(pin_count="foo", addr_width=2, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Pin count must be a positive integer, not 0"):
            gpio.Peripheral(pin_count=0, addr_width=2, data_width=8)

    def test_init_wrong_input_stages(self):
        with self.assertRaisesRegex(TypeError,
                r"Input stages must be a non-negative integer, not 'foo'"):
            gpio.Peripheral(pin_count=1, addr_width=2, data_width=8, input_stages="foo")
        with self.assertRaisesRegex(TypeError,
                r"Input stages must be a non-negative integer, not -1"):
            gpio.Peripheral(pin_count=1, addr_width=2, data_width=8, input_stages=-1)

    async def _csr_access(self, ctx, dut, addr, r_stb=0, w_stb=0, w_data=0, r_data=0):
        ctx.set(dut.bus.addr, addr)
        ctx.set(dut.bus.r_stb, r_stb)
        ctx.set(dut.bus.w_stb, w_stb)
        ctx.set(dut.bus.w_data, w_data)
        await ctx.tick()
        if r_stb:
            self.assertEqual(ctx.get(dut.bus.r_data), r_data)
        ctx.set(dut.bus.r_stb, 0)
        ctx.set(dut.bus.w_stb, 0)

    def test_sim(self):
        dut = gpio.Peripheral(pin_count=4, addr_width=2, data_width=8)

        mode_addr   = 0x0
        input_addr  = 0x1
        output_addr = 0x2
        setclr_addr = 0x3

        async def testbench(ctx):
            # INPUT_ONLY mode =====================================================================

            # - read Mode:
            await self._csr_access(ctx, dut, mode_addr, r_stb=1, r_data=0b00000000)
            for n in range(4):
                self.assertEqual(ctx.get(dut.alt_mode[n]), 0)
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - read Input:
            ctx.set(dut.pins[1].i, 1)
            ctx.set(dut.pins[3].i, 1)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            ctx.set(dut.pins[1].i, 0)
            ctx.set(dut.pins[3].i, 0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0xa)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 1)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x22)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
            self.assertEqual(ctx.get(dut.pins[0].o), 0)
            self.assertEqual(ctx.get(dut.pins[1].o), 1)
            self.assertEqual(ctx.get(dut.pins[2].o), 0)
            self.assertEqual(ctx.get(dut.pins[3].o), 1)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x44)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
            self.assertEqual(ctx.get(dut.pins[0].o), 0)
            self.assertEqual(ctx.get(dut.pins[1].o), 1)
            self.assertEqual(ctx.get(dut.pins[2].o), 0)
            self.assertEqual(ctx.get(dut.pins[3].o), 1)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0xff)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # PUSH_PULL mode ======================================================================

            # - write Mode:
            await self._csr_access(ctx, dut, mode_addr, w_stb=1, w_data=0b01010101)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.alt_mode[n]), 0)
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - read Input:
            ctx.set(dut.pins[1].i, 1)
            ctx.set(dut.pins[3].i, 1)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            ctx.set(dut.pins[1].i, 0)
            ctx.set(dut.pins[3].i, 0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0xa)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 1)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x22)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
            self.assertEqual(ctx.get(dut.pins[0].o), 0)
            self.assertEqual(ctx.get(dut.pins[1].o), 1)
            self.assertEqual(ctx.get(dut.pins[2].o), 0)
            self.assertEqual(ctx.get(dut.pins[3].o), 1)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x44)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
            self.assertEqual(ctx.get(dut.pins[0].o), 0)
            self.assertEqual(ctx.get(dut.pins[1].o), 1)
            self.assertEqual(ctx.get(dut.pins[2].o), 0)
            self.assertEqual(ctx.get(dut.pins[3].o), 1)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0xff)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # OPEN_DRAIN mode =====================================================================

            # - write Mode:
            await self._csr_access(ctx, dut, mode_addr, w_stb=1, w_data=0b10101010)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.alt_mode[n]), 0)
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - read Input:
            ctx.set(dut.pins[1].i, 1)
            ctx.set(dut.pins[3].i, 1)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            ctx.set(dut.pins[1].i, 0)
            ctx.set(dut.pins[3].i, 0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0xa)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x22)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.pins[0].oe), 1)
            self.assertEqual(ctx.get(dut.pins[1].oe), 0)
            self.assertEqual(ctx.get(dut.pins[2].oe), 1)
            self.assertEqual(ctx.get(dut.pins[3].oe), 0)
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x44)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.pins[0].oe), 1)
            self.assertEqual(ctx.get(dut.pins[1].oe), 0)
            self.assertEqual(ctx.get(dut.pins[2].oe), 1)
            self.assertEqual(ctx.get(dut.pins[3].oe), 0)
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0xff)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 1)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # ALTERNATE mode ======================================================================

            # - write Mode:
            await self._csr_access(ctx, dut, mode_addr, w_stb=1, w_data=0b11111111)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.alt_mode[n]), 1)
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - read Input:
            ctx.set(dut.pins[1].i, 1)
            ctx.set(dut.pins[3].i, 1)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            ctx.set(dut.pins[1].i, 0)
            ctx.set(dut.pins[3].i, 0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0xa)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 1)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x22)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
            self.assertEqual(ctx.get(dut.pins[0].o), 0)
            self.assertEqual(ctx.get(dut.pins[1].o), 1)
            self.assertEqual(ctx.get(dut.pins[2].o), 0)
            self.assertEqual(ctx.get(dut.pins[3].o), 1)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0x44)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
            self.assertEqual(ctx.get(dut.pins[0].o), 0)
            self.assertEqual(ctx.get(dut.pins[1].o), 1)
            self.assertEqual(ctx.get(dut.pins[2].o), 0)
            self.assertEqual(ctx.get(dut.pins[3].o), 1)

            # - write 0x0 to Output:
            await self._csr_access(ctx, dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            await self._csr_access(ctx, dut, setclr_addr, w_stb=1, w_data=0xff)
            await ctx.tick()
            for n in range(4):
                self.assertEqual(ctx.get(dut.pins[n].oe), 0)
                self.assertEqual(ctx.get(dut.pins[n].o), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_sim_without_input_sync(self):
        dut = gpio.Peripheral(pin_count=4, addr_width=2, data_width=8, input_stages=0)
        input_addr = 0x1

        async def testbench(ctx):
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)
            ctx.set(dut.pins[1].i, 1)
            ctx.set(dut.pins[3].i, 1)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0xa)
            ctx.set(dut.pins[1].i, 0)
            ctx.set(dut.pins[3].i, 0)
            await self._csr_access(ctx, dut, input_addr, r_stb=1, r_data=0x0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
