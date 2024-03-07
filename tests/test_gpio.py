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

    def _csr_access(self, dut, addr, r_stb=0, w_stb=0, w_data=0, r_data=0):
        yield dut.bus.addr.eq(addr)
        yield dut.bus.r_stb.eq(r_stb)
        yield dut.bus.w_stb.eq(w_stb)
        yield dut.bus.w_data.eq(w_data)
        yield Tick()
        if r_stb:
            self.assertEqual((yield dut.bus.r_data), r_data)
        yield dut.bus.r_stb.eq(0)
        yield dut.bus.w_stb.eq(0)

    def test_sim(self):
        dut = gpio.Peripheral(pin_count=4, addr_width=2, data_width=8)

        mode_addr   = 0x0
        input_addr  = 0x1
        output_addr = 0x2
        setclr_addr = 0x3

        def testbench():
            # INPUT_ONLY mode =====================================================================

            # - read Mode:
            yield from self._csr_access(dut, mode_addr, r_stb=1, r_data=0b00000000)
            for n in range(4):
                self.assertEqual((yield dut.alt_mode[n]), 0)
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - read Input:
            yield dut.pins[1].i.eq(1)
            yield dut.pins[3].i.eq(1)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield dut.pins[1].i.eq(0)
            yield dut.pins[3].i.eq(0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0xa)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 1)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x22)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
            self.assertEqual((yield dut.pins[0].o), 0)
            self.assertEqual((yield dut.pins[1].o), 1)
            self.assertEqual((yield dut.pins[2].o), 0)
            self.assertEqual((yield dut.pins[3].o), 1)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x44)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
            self.assertEqual((yield dut.pins[0].o), 0)
            self.assertEqual((yield dut.pins[1].o), 1)
            self.assertEqual((yield dut.pins[2].o), 0)
            self.assertEqual((yield dut.pins[3].o), 1)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0xff)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # PUSH_PULL mode ======================================================================

            # - write Mode:
            yield from self._csr_access(dut, mode_addr, w_stb=1, w_data=0b01010101)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.alt_mode[n]), 0)
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - read Input:
            yield dut.pins[1].i.eq(1)
            yield dut.pins[3].i.eq(1)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield dut.pins[1].i.eq(0)
            yield dut.pins[3].i.eq(0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0xa)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 1)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x22)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
            self.assertEqual((yield dut.pins[0].o), 0)
            self.assertEqual((yield dut.pins[1].o), 1)
            self.assertEqual((yield dut.pins[2].o), 0)
            self.assertEqual((yield dut.pins[3].o), 1)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x44)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
            self.assertEqual((yield dut.pins[0].o), 0)
            self.assertEqual((yield dut.pins[1].o), 1)
            self.assertEqual((yield dut.pins[2].o), 0)
            self.assertEqual((yield dut.pins[3].o), 1)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0xff)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # OPEN_DRAIN mode =====================================================================

            # - write Mode:
            yield from self._csr_access(dut, mode_addr, w_stb=1, w_data=0b10101010)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.alt_mode[n]), 0)
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - read Input:
            yield dut.pins[1].i.eq(1)
            yield dut.pins[3].i.eq(1)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield dut.pins[1].i.eq(0)
            yield dut.pins[3].i.eq(0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0xa)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x22)
            yield Tick()
            self.assertEqual((yield dut.pins[0].oe), 1)
            self.assertEqual((yield dut.pins[1].oe), 0)
            self.assertEqual((yield dut.pins[2].oe), 1)
            self.assertEqual((yield dut.pins[3].oe), 0)
            for n in range(4):
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x44)
            yield Tick()
            self.assertEqual((yield dut.pins[0].oe), 1)
            self.assertEqual((yield dut.pins[1].oe), 0)
            self.assertEqual((yield dut.pins[2].oe), 1)
            self.assertEqual((yield dut.pins[3].oe), 0)
            for n in range(4):
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0xff)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 1)
                self.assertEqual((yield dut.pins[n].o), 0)

            # ALTERNATE mode ======================================================================

            # - write Mode:
            yield from self._csr_access(dut, mode_addr, w_stb=1, w_data=0b11111111)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.alt_mode[n]), 1)
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - read Input:
            yield dut.pins[1].i.eq(1)
            yield dut.pins[3].i.eq(1)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield dut.pins[1].i.eq(0)
            yield dut.pins[3].i.eq(0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0xa)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)

            # - write 0xf to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0x0, w_stb=1, w_data=0xf)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 1)

            # - write 0x22 to SetClr (clear pins[0] and pins[2]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x22)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
            self.assertEqual((yield dut.pins[0].o), 0)
            self.assertEqual((yield dut.pins[1].o), 1)
            self.assertEqual((yield dut.pins[2].o), 0)
            self.assertEqual((yield dut.pins[3].o), 1)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0x44 to SetClr (set pins[1] and pins[3]):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0x44)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
            self.assertEqual((yield dut.pins[0].o), 0)
            self.assertEqual((yield dut.pins[1].o), 1)
            self.assertEqual((yield dut.pins[2].o), 0)
            self.assertEqual((yield dut.pins[3].o), 1)

            # - write 0x0 to Output:
            yield from self._csr_access(dut, output_addr, r_stb=1, r_data=0xa, w_stb=1, w_data=0x0)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

            # - write 0xff to SetClr (no-op):
            yield from self._csr_access(dut, setclr_addr, w_stb=1, w_data=0xff)
            yield Tick()
            for n in range(4):
                self.assertEqual((yield dut.pins[n].oe), 0)
                self.assertEqual((yield dut.pins[n].o), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_sim_without_input_sync(self):
        dut = gpio.Peripheral(pin_count=4, addr_width=2, data_width=8, input_stages=0)
        input_addr = 0x1

        def testbench():
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)
            yield dut.pins[1].i.eq(1)
            yield dut.pins[3].i.eq(1)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0xa)
            yield dut.pins[1].i.eq(0)
            yield dut.pins[3].i.eq(0)
            yield from self._csr_access(dut, input_addr, r_stb=1, r_data=0x0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()
