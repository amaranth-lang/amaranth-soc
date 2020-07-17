# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.back.pysim import *

from .. import csr
from ..csr.wishbone import *


class MockRegister(Elaboratable):
    def __init__(self, width):
        self.element = csr.Element(width, "rw")
        self.r_count = Signal(8)
        self.w_count = Signal(8)
        self.data    = Signal(width)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.element.r_stb):
            m.d.sync += self.r_count.eq(self.r_count + 1)
        m.d.comb += self.element.r_data.eq(self.data)

        with m.If(self.element.w_stb):
            m.d.sync += self.w_count.eq(self.w_count + 1)
            m.d.sync += self.data.eq(self.element.w_data)

        return m


class WishboneCSRBridgeTestCase(unittest.TestCase):
    def test_wrong_csr_bus(self):
        with self.assertRaisesRegex(ValueError,
                r"CSR bus must be an instance of CSRInterface, not 'foo'"):
            WishboneCSRBridge("foo")

    def test_wrong_csr_bus_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"CSR bus data width must be one of 8, 16, 32, 64, not 7"):
            WishboneCSRBridge(csr_bus=csr.Interface(addr_width=10, data_width=7))

    def test_narrow(self):
        mux   = csr.Multiplexer(addr_width=10, data_width=8)
        reg_1 = MockRegister(8)
        mux.add(reg_1.element)
        reg_2 = MockRegister(16)
        mux.add(reg_2.element)
        dut   = WishboneCSRBridge(mux.bus)

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.sel.eq(0b1)

            yield dut.wb_bus.we.eq(1)

            yield dut.wb_bus.adr.eq(0)
            yield dut.wb_bus.stb.eq(1)
            yield dut.wb_bus.dat_w.eq(0x55)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg_1.r_count), 0)
            self.assertEqual((yield reg_1.w_count), 1)
            self.assertEqual((yield reg_1.data), 0x55)

            yield dut.wb_bus.adr.eq(1)
            yield dut.wb_bus.stb.eq(1)
            yield dut.wb_bus.dat_w.eq(0xaa)
            yield
            yield
            yield
            yield dut.wb_bus.stb.eq(0)
            self.assertEqual((yield dut.wb_bus.ack), 1)
            yield
            self.assertEqual((yield reg_2.r_count), 0)
            self.assertEqual((yield reg_2.w_count), 0)
            self.assertEqual((yield reg_2.data), 0)

            yield dut.wb_bus.adr.eq(2)
            yield dut.wb_bus.stb.eq(1)
            yield dut.wb_bus.dat_w.eq(0xbb)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg_2.r_count), 0)
            self.assertEqual((yield reg_2.w_count), 1)
            self.assertEqual((yield reg_2.data), 0xbbaa)

            yield dut.wb_bus.we.eq(0)

            yield dut.wb_bus.adr.eq(0)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x55)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg_1.r_count), 1)
            self.assertEqual((yield reg_1.w_count), 1)

            yield dut.wb_bus.adr.eq(1)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0xaa)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg_2.r_count), 1)
            self.assertEqual((yield reg_2.w_count), 1)

            yield reg_2.data.eq(0x33333)

            yield dut.wb_bus.adr.eq(2)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0xbb)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg_2.r_count), 1)
            self.assertEqual((yield reg_2.w_count), 1)

        m = Module()
        m.submodules += mux, reg_1, reg_2, dut
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()

    def test_wide(self):
        mux = csr.Multiplexer(addr_width=10, data_width=8)
        reg = MockRegister(32)
        mux.add(reg.element)
        dut = WishboneCSRBridge(mux.bus, data_width=32)

        def sim_test():
            yield dut.wb_bus.cyc.eq(1)
            yield dut.wb_bus.adr.eq(0)

            yield dut.wb_bus.we.eq(1)

            yield dut.wb_bus.dat_w.eq(0x44332211)
            yield dut.wb_bus.sel.eq(0b1111)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg.r_count), 0)
            self.assertEqual((yield reg.w_count), 1)
            self.assertEqual((yield reg.data), 0x44332211)

            # partial write
            yield dut.wb_bus.dat_w.eq(0xaabbccdd)
            yield dut.wb_bus.sel.eq(0b0110)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg.r_count), 0)
            self.assertEqual((yield reg.w_count), 1)
            self.assertEqual((yield reg.data), 0x44332211)

            yield dut.wb_bus.we.eq(0)

            yield dut.wb_bus.sel.eq(0b1111)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x44332211)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg.r_count), 1)
            self.assertEqual((yield reg.w_count), 1)

            yield reg.data.eq(0xaaaaaaaa)

            # partial read
            yield dut.wb_bus.sel.eq(0b0110)
            yield dut.wb_bus.stb.eq(1)
            yield
            yield
            yield
            yield
            yield
            yield
            self.assertEqual((yield dut.wb_bus.ack), 1)
            self.assertEqual((yield dut.wb_bus.dat_r), 0x00332200)
            yield dut.wb_bus.stb.eq(0)
            yield
            self.assertEqual((yield reg.r_count), 1)
            self.assertEqual((yield reg.w_count), 1)

        m = Module()
        m.submodules += mux, reg, dut
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_sync_process(sim_test)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()
