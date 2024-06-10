# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import *

from amaranth_soc import csr
from amaranth_soc.csr.wishbone import *
from amaranth_soc.memory import MemoryMap


class _MockRegister(wiring.Component):
    def __init__(self, width, name):
        super().__init__({
            "element": Out(csr.Element.Signature(width, "rw")),
            "r_count": Out(unsigned(8)),
            "w_count": Out(unsigned(8)),
            "data":    Out(width)
        })
        self._name = name

    def elaborate(self, platform):
        m = Module()

        with m.If(self.element.r_stb):
            m.d.sync += self.r_count.eq(self.r_count + 1)
        m.d.comb += self.element.r_data.eq(self.data)

        with m.If(self.element.w_stb):
            m.d.sync += self.w_count.eq(self.w_count + 1)
            m.d.sync += self.data.eq(self.element.w_data)

        return m

    def __repr__(self):
        return f"_MockRegister('{self._name}')"


class WishboneCSRBridgeTestCase(unittest.TestCase):
    def test_wrong_csr_bus(self):
        with self.assertRaisesRegex(TypeError,
                r"CSR bus must be an instance of csr\.Interface, not 'foo'"):
            WishboneCSRBridge("foo")

    def test_wrong_csr_bus_data_width(self):
        csr_bus = csr.Signature(addr_width=10, data_width=7).create()
        with self.assertRaisesRegex(ValueError,
                r"CSR bus data width must be one of 8, 16, 32, 64, not 7"):
            WishboneCSRBridge(csr_bus)

    def test_narrow(self):
        reg_1 = _MockRegister( 8, name="reg_1")
        reg_2 = _MockRegister(16, name="reg_2")

        memory_map = MemoryMap(addr_width=10, data_width=8)
        memory_map.add_resource(reg_1, name=("reg_1",), size=1)
        memory_map.add_resource(reg_2, name=("reg_2",), size=2)

        mux = csr.Multiplexer(memory_map)
        dut = WishboneCSRBridge(mux.bus)

        async def testbench(ctx):
            ctx.set(dut.wb_bus.cyc, 1)
            ctx.set(dut.wb_bus.sel, 0b1)
            ctx.set(dut.wb_bus.we, 1)

            ctx.set(dut.wb_bus.adr, 0)
            ctx.set(dut.wb_bus.stb, 1)
            ctx.set(dut.wb_bus.dat_w, 0x55)
            await ctx.tick().repeat(2)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg_1.r_count), 0)
            self.assertEqual(ctx.get(reg_1.w_count), 1)
            self.assertEqual(ctx.get(reg_1.data), 0x55)

            ctx.set(dut.wb_bus.adr, 1)
            ctx.set(dut.wb_bus.stb, 1)
            ctx.set(dut.wb_bus.dat_w, 0xaa)
            await ctx.tick().repeat(2)
            ctx.set(dut.wb_bus.stb, 0)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg_2.r_count), 0)
            self.assertEqual(ctx.get(reg_2.w_count), 0)
            self.assertEqual(ctx.get(reg_2.data), 0)

            ctx.set(dut.wb_bus.adr, 2)
            ctx.set(dut.wb_bus.stb, 1)
            ctx.set(dut.wb_bus.dat_w, 0xbb)
            await ctx.tick().repeat(2)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg_2.r_count), 0)
            self.assertEqual(ctx.get(reg_2.w_count), 1)
            self.assertEqual(ctx.get(reg_2.data), 0xbbaa)

            ctx.set(dut.wb_bus.we, 0)

            ctx.set(dut.wb_bus.adr, 0)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(2)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            self.assertEqual(ctx.get(dut.wb_bus.dat_r), 0x55)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg_1.r_count), 1)
            self.assertEqual(ctx.get(reg_1.w_count), 1)

            ctx.set(dut.wb_bus.adr, 1)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(2)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            self.assertEqual(ctx.get(dut.wb_bus.dat_r), 0xaa)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg_2.r_count), 1)
            self.assertEqual(ctx.get(reg_2.w_count), 1)

            ctx.set(reg_2.data, 0x33333)

            ctx.set(dut.wb_bus.adr, 2)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(2)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            self.assertEqual(ctx.get(dut.wb_bus.dat_r), 0xbb)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg_2.r_count), 1)
            self.assertEqual(ctx.get(reg_2.w_count), 1)

        m = Module()
        m.submodules.reg_1 = reg_1
        m.submodules.reg_2 = reg_2
        m.submodules.mux = mux
        m.submodules.dut = dut

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_wide(self):
        reg = _MockRegister(32, name="reg")

        memory_map = MemoryMap(addr_width=10, data_width=8)
        memory_map.add_resource(reg, name=("reg",), size=4)

        mux = csr.Multiplexer(memory_map)
        dut = WishboneCSRBridge(mux.bus, data_width=32)

        async def testbench(ctx):
            ctx.set(dut.wb_bus.cyc, 1)
            ctx.set(dut.wb_bus.adr, 0)
            ctx.set(dut.wb_bus.we, 1)

            ctx.set(dut.wb_bus.dat_w, 0x44332211)
            ctx.set(dut.wb_bus.sel, 0b1111)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(5)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg.r_count), 0)
            self.assertEqual(ctx.get(reg.w_count), 1)
            self.assertEqual(ctx.get(reg.data), 0x44332211)

            # partial write
            ctx.set(dut.wb_bus.dat_w, 0xaabbccdd)
            ctx.set(dut.wb_bus.sel, 0b0110)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(5)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg.r_count), 0)
            self.assertEqual(ctx.get(reg.w_count), 1)
            self.assertEqual(ctx.get(reg.data), 0x44332211)

            ctx.set(dut.wb_bus.we, 0)

            ctx.set(dut.wb_bus.sel, 0b1111)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(5)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            self.assertEqual(ctx.get(dut.wb_bus.dat_r), 0x44332211)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg.r_count), 1)
            self.assertEqual(ctx.get(reg.w_count), 1)

            ctx.set(reg.data, 0xaaaaaaaa)

            # partial read
            ctx.set(dut.wb_bus.sel, 0b0110)
            ctx.set(dut.wb_bus.stb, 1)
            await ctx.tick().repeat(5)
            self.assertEqual(ctx.get(dut.wb_bus.ack), 1)
            self.assertEqual(ctx.get(dut.wb_bus.dat_r), 0x00332200)
            ctx.set(dut.wb_bus.stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.wb_bus.ack), 0)
            self.assertEqual(ctx.get(reg.r_count), 1)
            self.assertEqual(ctx.get(reg.w_count), 1)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        m.submodules.dut = dut

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
