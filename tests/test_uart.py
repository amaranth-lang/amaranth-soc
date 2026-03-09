# amaranth: UnusedElaboratable=no
import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect
from amaranth.lib.fifo import SyncFIFO
from amaranth.sim import *

from amaranth_soc import uart


async def _csr_access(self, ctx, dut, addr, r_stb=0, r_data=0, w_stb=0, w_data=0):
    ctx.set(dut.bus.addr, addr)
    ctx.set(dut.bus.r_stb, r_stb)
    ctx.set(dut.bus.w_stb, w_stb)
    ctx.set(dut.bus.w_data, w_data)
    await ctx.tick()
    if r_stb:
        self.assertEqual(ctx.get(dut.bus.r_data), r_data)
    ctx.set(dut.bus.r_stb, 0)
    ctx.set(dut.bus.w_stb, 0)


class RxPeripheralTestCase(unittest.TestCase):
    def test_init(self):
        dut_1 = uart.RxPeripheral(addr_width=3, data_width=8)
        self.assertEqual(dut_1.phy_config_shape, unsigned(16))
        self.assertEqual(dut_1.phy_config_init, 0)
        self.assertEqual(dut_1.symbol_shape, unsigned(8))
        self.assertEqual(dut_1.bus.addr_width, 3)
        self.assertEqual(dut_1.bus.data_width, 8)
        dut_2 = uart.RxPeripheral(addr_width=8, data_width=16,
                                  phy_config_shape=unsigned(32), phy_config_init=0xa5a5a5a5,
                                  symbol_shape=unsigned(16))
        self.assertEqual(dut_2.phy_config_shape, unsigned(32))
        self.assertEqual(dut_2.phy_config_init, 0xa5a5a5a5)
        self.assertEqual(dut_2.symbol_shape, unsigned(16))
        self.assertEqual(dut_2.bus.addr_width, 8)
        self.assertEqual(dut_2.bus.data_width, 16)

    def test_sim(self):
        dut = uart.RxPeripheral(addr_width=3, data_width=8, phy_config_init=0xa455)

        config_addr     = 0x0
        phy_config_addr = 0x2
        status_addr     = 0x4
        data_addr       = 0x5

        async def testbench(ctx):
            # PHY disabled (initial state) ========================================================

            self.assertEqual(ctx.get(dut.phy.rst), 1)

            # - read Config (enable=0):
            await _csr_access(self, ctx, dut, config_addr, r_stb=1, r_data=0)

            self.assertEqual(ctx.get(dut.phy.config), 0xa455)

            # - read PhyConfig (=0xa455) and write 0x0001:
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x55, w_stb=1,
                              w_data=0x01)
            self.assertEqual(ctx.get(dut.phy.config), 0xa455)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0xa4, w_stb=1,
                              w_data=0x00)
            self.assertEqual(ctx.get(dut.phy.config), 0xa455)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.config), 0x0001)

            # - read PhyConfig (=0x0001):
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x01)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0x00)

            # - read Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b000)

            # PHY disabled -> enabled =============================================================

            self.assertEqual(ctx.get(dut.phy.rst), 1)

            # - read Config (enable=0) and write 1:
            await _csr_access(self, ctx, dut, config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            self.assertEqual(ctx.get(dut.phy.rst), 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.rst), 0)

            # PHY enabled =========================================================================

            self.assertEqual(ctx.get(dut.phy.config), 0x0001)

            # - read PhyConfig (=0x0001) and write 0xa455:
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x01, w_stb=1,
                              w_data=0x55)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0x00, w_stb=1,
                              w_data=0xa4)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.config), 0x0001)

            # - read PhyConfig (=0x0001):
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x01)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0x00)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.phy.symbols.ready), 0)

            ctx.set(dut.phy.symbols.payload, ord("a"))
            ctx.set(dut.phy.symbols.valid, 1)

            # - read Status (ready=1, overflow=0, error=0):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b001)

            # - read Data (="a"):
            ctx.set(dut.bus.addr, data_addr)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.bus.r_data), ord("a"))
            self.assertEqual(ctx.get(dut.phy.symbols.ready), 1)
            ctx.set(dut.bus.r_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.symbols.ready), 0)
            ctx.set(dut.phy.symbols.valid, 0)

            # - read Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b000)

            ctx.set(dut.phy.error, 1)
            ctx.set(dut.phy.overflow, 1)
            await ctx.tick()
            ctx.set(dut.phy.error, 0)
            ctx.set(dut.phy.overflow, 0)

            # - read Status (ready=0, overflow=1, error=1):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b110)

            ctx.set(dut.phy.symbols.payload, ord("b"))
            ctx.set(dut.phy.symbols.valid, 1)

            # - read Status (ready=1, overflow=1, error=1):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b111)

            # PHY enabled -> disabled =============================================================

            self.assertEqual(ctx.get(dut.phy.rst), 0)

            # - read Config (enable=1) and write 0:
            await _csr_access(self, ctx, dut, config_addr, r_stb=1, r_data=1, w_stb=1, w_data=0)
            self.assertEqual(ctx.get(dut.phy.rst), 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.rst), 1)

            ctx.set(dut.phy.symbols.valid, 0)

            # - read Status (ready=0, overflow=1, error=1) and write 0b110:
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b110, w_stb=1, w_data=0b110)
            await ctx.tick()

            # - read Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0b000)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


class TxPeripheralTestCase(unittest.TestCase):
    def test_init(self):
        dut_1 = uart.TxPeripheral(addr_width=3, data_width=8)
        self.assertEqual(dut_1.phy_config_shape, unsigned(16))
        self.assertEqual(dut_1.phy_config_init, 0)
        self.assertEqual(dut_1.symbol_shape, unsigned(8))
        self.assertEqual(dut_1.bus.addr_width, 3)
        self.assertEqual(dut_1.bus.data_width, 8)
        dut_2 = uart.TxPeripheral(addr_width=8, data_width=16,
                                  phy_config_shape=unsigned(32), phy_config_init=0xa5a5a5a5,
                                  symbol_shape=unsigned(16))
        self.assertEqual(dut_2.phy_config_shape, unsigned(32))
        self.assertEqual(dut_2.phy_config_init, 0xa5a5a5a5)
        self.assertEqual(dut_2.symbol_shape, unsigned(16))
        self.assertEqual(dut_2.bus.addr_width, 8)
        self.assertEqual(dut_2.bus.data_width, 16)

    def test_sim(self):
        dut = uart.TxPeripheral(addr_width=3, data_width=8, phy_config_init=0xa455)

        config_addr     = 0x0
        phy_config_addr = 0x2
        status_addr     = 0x4
        data_addr       = 0x5

        async def testbench(ctx):
            # PHY disabled (initial state) ========================================================

            self.assertEqual(ctx.get(dut.phy.rst), 1)
            ctx.set(dut.phy.symbols.ready, 0)

            # - read Config (enable=0):
            await _csr_access(self, ctx, dut, config_addr, r_stb=1, r_data=0)

            self.assertEqual(ctx.get(dut.phy.config), 0xa455)

            # - read PhyConfig (=0xa455) and write 0x0001:
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x55, w_stb=1,
                              w_data=0x01)
            self.assertEqual(ctx.get(dut.phy.config), 0xa455)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0xa4, w_stb=1,
                              w_data=0x00)
            self.assertEqual(ctx.get(dut.phy.config), 0xa455)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.config), 0x0001)

            # - read PhyConfig (=0x0001):
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x01)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0x00)

            # - read Status (ready=0):
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0)

            # PHY disabled -> enabled =============================================================

            self.assertEqual(ctx.get(dut.phy.rst), 1)

            # - read Config (enable=0) and write 1:
            await _csr_access(self, ctx, dut, config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            self.assertEqual(ctx.get(dut.phy.rst), 1)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.rst), 0)

            # PHY enabled =========================================================================

            self.assertEqual(ctx.get(dut.phy.config), 0x0001)

            # - read PhyConfig (=0x0001) and write 0xa455:
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x01, w_stb=1,
                              w_data=0x55)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0x00, w_stb=1,
                              w_data=0xa4)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.config), 0x0001)

            # - read PhyConfig (=0x0001):
            await _csr_access(self, ctx, dut, phy_config_addr+0, r_stb=1, r_data=0x01)
            await _csr_access(self, ctx, dut, phy_config_addr+1, r_stb=1, r_data=0x00)
            await ctx.tick()

            # - read Status (ready=0)
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0)

            ctx.set(dut.phy.symbols.ready, 1)

            # - read Status (ready=1)
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=1)

            # - write "a" to Data:
            ctx.set(dut.bus.addr, data_addr)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, ord("a"))
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.symbols.valid), 1)
            self.assertEqual(ctx.get(dut.phy.symbols.payload), ord("a"))
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.symbols.valid), 0)

            ctx.set(dut.phy.symbols.ready, 0)

            # - read Status (ready=0)
            await _csr_access(self, ctx, dut, status_addr, r_stb=1, r_data=0)

            # PHY enabled -> disabled =============================================================

            self.assertEqual(ctx.get(dut.phy.rst), 0)

            # - read Config (enable=1) and write 0:
            await _csr_access(self, ctx, dut, config_addr, r_stb=1, r_data=1, w_stb=1, w_data=0)
            self.assertEqual(ctx.get(dut.phy.rst), 0)
            await ctx.tick()
            self.assertEqual(ctx.get(dut.phy.rst), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


class _LoopbackPHY(wiring.Component):
    rx: In(uart.RxPhySignature(phy_config_shape=unsigned(16), symbol_shape=unsigned(8)))
    tx: In(uart.TxPhySignature(phy_config_shape=unsigned(16), symbol_shape=unsigned(8)))

    def elaborate(self, platform):
        m = Module()

        fifo = SyncFIFO(width=8, depth=4)
        m.submodules.fifo = ResetInserter(self.rx.rst | self.tx.rst)(fifo)

        m.d.comb += [
            self.tx.symbols.ready.eq(fifo.w_rdy & ~self.tx.rst),
            fifo.w_en.eq(self.tx.symbols.valid),
            fifo.w_data.eq(self.tx.symbols.payload),

            self.rx.symbols.valid.eq(fifo.r_rdy),
            self.rx.symbols.payload.eq(fifo.r_data),
            fifo.r_en.eq(self.rx.symbols.ready),

            self.rx.overflow.eq(fifo.w_en & ~fifo.w_rdy),
        ]

        return m


class PeripheralTestCase(unittest.TestCase):
    def test_init(self):
        dut_1 = uart.Peripheral(addr_width=4, data_width=8)
        self.assertEqual(dut_1.phy_config_shape, unsigned(16))
        self.assertEqual(dut_1.phy_config_init, 0)
        self.assertEqual(dut_1.symbol_shape, unsigned(8))
        self.assertEqual(dut_1.bus.addr_width, 4)
        self.assertEqual(dut_1.bus.data_width, 8)
        dut_2 = uart.Peripheral(addr_width=8, data_width=16,
                                phy_config_shape=unsigned(32), phy_config_init=0xa5a5a5a5,
                                symbol_shape=unsigned(16))
        self.assertEqual(dut_2.phy_config_shape, unsigned(32))
        self.assertEqual(dut_2.phy_config_init, 0xa5a5a5a5)
        self.assertEqual(dut_2.symbol_shape, unsigned(16))
        self.assertEqual(dut_2.bus.addr_width, 8)
        self.assertEqual(dut_2.bus.data_width, 16)

    def test_init_wrong_addr_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Address width must be a positive integer, not 'foo'"):
            uart.Peripheral(addr_width="foo", data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Address width must be a positive integer, not 0"):
            uart.Peripheral(addr_width=0, data_width=8)

    def test_sim(self):
        dut = uart.Peripheral(addr_width=5, data_width=8)
        phy = _LoopbackPHY()

        m = Module()
        m.submodules.dut = dut
        m.submodules.phy = phy

        connect(m, dut.rx, phy.rx)
        connect(m, dut.tx, phy.tx)

        rx_config_addr     = 0x00
        rx_phy_config_addr = 0x02
        rx_status_addr     = 0x04
        rx_data_addr       = 0x05

        tx_config_addr     = 0x10
        tx_phy_config_addr = 0x12
        tx_status_addr     = 0x14
        tx_data_addr       = 0x15

        async def testbench(ctx):
            # PHY disabled ========================================================================

            # - read rx.Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # - read tx.Status (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - write "x" to tx.Data:
            await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord("x"))
            await ctx.tick()

            # - read rx.Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY disabled -> enabled =============================================================

            # - read rx.Config (enable=0) and write 1:
            await _csr_access(self, ctx, dut, rx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read tx.Config (enable=0) and write 1:
            await _csr_access(self, ctx, dut, tx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read rx.Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY enabled =========================================================================

            for c in "abcd":
                # - read tx.Status (ready=1):
                await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=1)

                # - write c to tx.Data:
                await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord(c))
                await ctx.tick()

            # - read rx.Status (ready=1, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b001)

            # - read tx.Status (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - write "e" to tx.Data:
            await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord("e"))
            await ctx.tick()

            # - read rx.Status (ready=1, overflow=1, error=0) and write 0b010:
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b011, w_stb=1,
                              w_data=0b010)
            await ctx.tick()

            for c in "abcd":
                # - read rx.Status (ready=1, overflow=0, error=0):
                await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b001)

                # - read rx.Data (=c)
                await _csr_access(self, ctx, dut, rx_data_addr, r_stb=1, r_data=ord(c))

            # - read rx.Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY enabled -> disabled =============================================================

            for c in "efgh":
                # - read tx.Status (ready=1):
                await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=1)

                # - write c to tx.Data:
                await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord(c))
                await ctx.tick()

            # - read tx.Status (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - read rx.Status (ready=1, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b001)

            # - read rx.Config (enable=1) and write 0:
            await _csr_access(self, ctx, dut, rx_config_addr, r_stb=1, r_data=1, w_stb=1, w_data=0)
            await ctx.tick()

            # - read tx.Config (enable=1) and write 0:
            await _csr_access(self, ctx, dut, tx_config_addr, r_stb=1, r_data=1, w_stb=1, w_data=0)
            await ctx.tick()

            # - read tx.Status (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - read rx.Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY disabled -> enabled =============================================================

            # - read rx.Config (enable=0) and write 1:
            await _csr_access(self, ctx, dut, rx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read tx.Config (enable=0) and write 1:
            await _csr_access(self, ctx, dut, tx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read tx.Status (ready=1):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=1)

            # - read rx.Status (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
