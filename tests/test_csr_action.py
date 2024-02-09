# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.sim import *

from amaranth_soc.csr import action


class RTestCase(unittest.TestCase):
    def test_simple(self):
        f = action.R(unsigned(4))
        self.assertEqual(f.r_data.shape(), unsigned(4))
        self.assertTrue(f.port.access.readable())
        self.assertFalse(f.port.access.writable())

    def test_sim(self):
        dut = action.R(unsigned(4))

        def process():
            yield dut.r_data.eq(0xa)
            yield dut.port.r_stb.eq(1)
            yield Settle()
            self.assertEqual((yield dut.port.r_data), 0xa)
            self.assertEqual((yield dut.r_stb), 1)

        sim = Simulator(dut)
        sim.add_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class WTestCase(unittest.TestCase):
    def test_simple(self):
        f = action.W(unsigned(4))
        self.assertEqual(f.w_data.shape(), unsigned(4))
        self.assertFalse(f.port.access.readable())
        self.assertTrue(f.port.access.writable())

    def test_sim(self):
        dut = action.W(unsigned(4))

        def process():
            yield dut.port.w_data.eq(0xa)
            yield dut.port.w_stb.eq(1)
            yield Settle()
            self.assertEqual((yield dut.w_data), 0xa)
            self.assertEqual((yield dut.w_stb), 1)

        sim = Simulator(dut)
        sim.add_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class RWTestCase(unittest.TestCase):
    def test_simple(self):
        f4 = action.RW(unsigned(4), reset=0x5)
        self.assertEqual(f4.data.shape(), unsigned(4))
        self.assertEqual(f4.reset, 0x5)
        self.assertTrue(f4.port.access.readable())
        self.assertTrue(f4.port.access.writable())

        f8 = action.RW(signed(8))
        self.assertEqual(f8.data.shape(), signed(8))
        self.assertEqual(f8.reset, 0)
        self.assertTrue(f8.port.access.readable())
        self.assertTrue(f8.port.access.writable())

    def test_sim(self):
        dut = action.RW(unsigned(4), reset=0x5)

        def process():
            self.assertEqual((yield dut.port.r_data), 0x5)
            self.assertEqual((yield dut.data), 0x5)
            yield dut.port.w_stb .eq(1)
            yield dut.port.w_data.eq(0xa)
            yield
            yield Settle()
            self.assertEqual((yield dut.port.r_data), 0xa)
            self.assertEqual((yield dut.data), 0xa)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class RW1CTestCase(unittest.TestCase):
    def test_simple(self):
        f4 = action.RW1C(unsigned(4), reset=0x5)
        self.assertEqual(f4.data.shape(), unsigned(4))
        self.assertEqual(f4.set .shape(), unsigned(4))
        self.assertEqual(f4.reset, 0x5)
        self.assertTrue(f4.port.access.readable())
        self.assertTrue(f4.port.access.writable())

        f8 = action.RW1C(signed(8))
        self.assertEqual(f8.data.shape(), signed(8))
        self.assertEqual(f8.set .shape(), signed(8))
        self.assertEqual(f8.reset, 0)
        self.assertTrue(f8.port.access.readable())
        self.assertTrue(f8.port.access.writable())

    def test_sim(self):
        dut = action.RW1C(unsigned(4), reset=0xf)

        def process():
            self.assertEqual((yield dut.port.r_data), 0xf)
            self.assertEqual((yield dut.data), 0xf)
            yield dut.port.w_stb .eq(1)
            yield dut.port.w_data.eq(0x5)
            yield
            yield Settle()
            self.assertEqual((yield dut.port.r_data), 0xa)
            self.assertEqual((yield dut.data), 0xa)

            yield dut.port.w_data.eq(0x3)
            yield dut.set.eq(0x4)
            yield
            yield Settle()
            self.assertEqual((yield dut.port.r_data), 0xc)
            self.assertEqual((yield dut.data), 0xc)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class RW1STestCase(unittest.TestCase):
    def test_simple(self):
        f4 = action.RW1S(unsigned(4), reset=0x5)
        self.assertEqual(f4.data .shape(), unsigned(4))
        self.assertEqual(f4.clear.shape(), unsigned(4))
        self.assertEqual(f4.reset, 0x5)
        self.assertTrue(f4.port.access.readable())
        self.assertTrue(f4.port.access.writable())

        f8 = action.RW1S(signed(8))
        self.assertEqual(f8.data .shape(), signed(8))
        self.assertEqual(f8.clear.shape(), signed(8))
        self.assertEqual(f8.reset, 0)
        self.assertTrue(f8.port.access.readable())
        self.assertTrue(f8.port.access.writable())

    def test_sim(self):
        dut = action.RW1S(unsigned(4), reset=0x5)

        def process():
            self.assertEqual((yield dut.port.r_data), 0x5)
            self.assertEqual((yield dut.data), 0x5)
            yield dut.port.w_stb .eq(1)
            yield dut.port.w_data.eq(0xa)
            yield
            yield Settle()
            self.assertEqual((yield dut.port.r_data), 0xf)
            self.assertEqual((yield dut.data), 0xf)

            yield dut.port.w_data.eq(0x3)
            yield dut.clear.eq(0x7)
            yield
            yield Settle()
            self.assertEqual((yield dut.port.r_data), 0xb)
            self.assertEqual((yield dut.data), 0xb)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class ResRAW0TestCase(unittest.TestCase):
    def test_simple(self):
        f = action.ResRAW0(unsigned(4))
        self.assertEqual(f.port.shape, unsigned(4))
        self.assertFalse(f.port.access.readable())
        self.assertFalse(f.port.access.writable())
        self.assertIsInstance(f.elaborate(platform=None), Module)

class ResRAWLTestCase(unittest.TestCase):
    def test_simple(self):
        f = action.ResRAWL(unsigned(4))
        self.assertEqual(f.port.shape, unsigned(4))
        self.assertFalse(f.port.access.readable())
        self.assertFalse(f.port.access.writable())
        self.assertIsInstance(f.elaborate(platform=None), Module)

class ResR0WATestCase(unittest.TestCase):
    def test_simple(self):
        f = action.ResR0WA(unsigned(4))
        self.assertEqual(f.port.shape, unsigned(4))
        self.assertFalse(f.port.access.readable())
        self.assertFalse(f.port.access.writable())
        self.assertIsInstance(f.elaborate(platform=None), Module)

class ResR0W0TestCase(unittest.TestCase):
    def test_simple(self):
        f = action.ResR0W0(unsigned(4))
        self.assertEqual(f.port.shape, unsigned(4))
        self.assertFalse(f.port.access.readable())
        self.assertFalse(f.port.access.writable())
        self.assertIsInstance(f.elaborate(platform=None), Module)
