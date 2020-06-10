# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.back.pysim import *

from ..csr.bus import *
from ..csr.periph import *


def simulation_test(dut, process):
    with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        sim.run()


class PeripheralTestCase(unittest.TestCase):
    def test_periph_name(self):
        class Wrapper(Peripheral):
            def __init__(self):
                super().__init__()
        periph_0 = Wrapper()
        periph_1 = Peripheral(name="periph_1")
        self.assertEqual(periph_0.name, "periph_0")
        self.assertEqual(periph_1.name, "periph_1")

    def test_periph_name_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            periph = Peripheral(name=2)

    def test_set_csr_bus_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(TypeError,
                r"CSR bus interface must be an instance of csr.Interface, not 'foo'"):
            periph.csr_bus = "foo"

    def test_get_csr_bus_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral <.*> does not have a CSR bus interface"):
            periph.csr_bus

    def test_set_irq_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(TypeError,
                r"IRQ line must be an instance of IRQLine, not 'foo'"):
            periph.irq = "foo"

    def test_get_irq_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral <.*> does not have an IRQ line"):
            periph.irq

    def test_iter_csr_registers(self):
        periph = Peripheral(src_loc_at=0)
        csr_0  = periph.csr(1, "r")
        csr_1  = periph.csr(8, "rw", addr=0x4, alignment=2)
        self.assertEqual(
            (csr_0.name, csr_0.width, csr_0.access),
            ("periph_csr_0", 1, Element.Access.R)
        )
        self.assertEqual(
            (csr_1.name, csr_1.width, csr_1.access),
            ("periph_csr_1", 8, Element.Access.RW)
        )
        self.assertEqual(list(periph.csr_registers()), [
            (csr_0, None, 0),
            (csr_1,  0x4, 2),
        ])

    def test_csr_name_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            periph.csr(1, "r", name=2)

    def test_iter_events(self):
        periph = Peripheral(src_loc_at=0)
        ev_0 = periph.event()
        ev_1 = periph.event(mode="rise")
        self.assertEqual((ev_0.name, ev_0.mode), ("ev_0", "level"))
        self.assertEqual((ev_1.name, ev_1.mode), ("ev_1", "rise"))
        self.assertEqual(list(periph.events()), [
            ev_0,
            ev_1,
        ])

    def test_event_name_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            periph.event(name=2)

    def test_event_mode_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(ValueError,
                r"Invalid trigger mode 'foo'; must be one of level, rise, fall"):
            periph.event(mode="foo")


class PeripheralBridgeTestCase(unittest.TestCase):
    def test_periph_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Peripheral must be an instance of Peripheral, not 'foo'"):
            PeripheralBridge('foo', data_width=8, alignment=0)


class PeripheralSimulationTestCase(unittest.TestCase):
    def test_csrs(self):
        class TestPeripheral(Peripheral, Elaboratable):
            def __init__(self):
                super().__init__()
                self.csr_0   = self.csr(8, "r")
                self.csr_1   = self.csr(8, "r", addr=8, alignment=4)
                self.csr_2   = self.csr(8, "w")
                self._bridge = self.csr_bridge(data_width=8, alignment=0)
                self.csr_bus = self._bridge.bus

            def elaborate(self, platform):
                m = Module()
                m.submodules.bridge = self._bridge
                return m

        dut = TestPeripheral()

        def process():
            yield dut.csr_0.r_data.eq(0xa)
            yield dut.csr_1.r_data.eq(0xb)

            yield dut.csr_bus.addr.eq(0)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            self.assertEqual((yield dut.csr_0.r_stb), 1)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0xa)

            yield dut.csr_bus.addr.eq(8)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            self.assertEqual((yield dut.csr_1.r_stb), 1)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0xb)

            yield dut.csr_bus.addr.eq(24)
            yield dut.csr_bus.w_stb.eq(1)
            yield dut.csr_bus.w_data.eq(0xc)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield
            self.assertEqual((yield dut.csr_2.w_stb), 1)
            self.assertEqual((yield dut.csr_2.w_data), 0xc)

        simulation_test(dut, process)

    def test_events(self):
        class TestPeripheral(Peripheral, Elaboratable):
            def __init__(self):
                super().__init__()
                self.ev_0    = self.event()
                self.ev_1    = self.event(mode="rise")
                self.ev_2    = self.event(mode="fall")
                self._bridge = self.csr_bridge(data_width=8)
                self.csr_bus = self._bridge.bus
                self.irq     = self._bridge.irq

            def elaborate(self, platform):
                m = Module()
                m.submodules.bridge = self._bridge
                return m

        dut = TestPeripheral()

        ev_status_addr  = 0x0
        ev_pending_addr = 0x1
        ev_enable_addr  = 0x2

        def process():
            yield dut.ev_0.stb.eq(1)
            yield dut.ev_1.stb.eq(0)
            yield dut.ev_2.stb.eq(1)
            yield
            self.assertEqual((yield dut.irq), 0)

            # read ev_status, check that ev_0 and ev_2 are active
            yield dut.csr_bus.addr.eq(ev_status_addr)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0b101)
            yield

            # enable all events, check that IRQ line goes high
            yield dut.csr_bus.addr.eq(ev_enable_addr)
            yield dut.csr_bus.w_data.eq(0b111)
            yield dut.csr_bus.w_stb.eq(1)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 1)

            # clear pending ev_0
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.w_data.eq(0b001)
            yield dut.csr_bus.w_stb.eq(1)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield

            # check that ev_0 is still pending, and IRQ line is still high
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0b001)
            self.assertEqual((yield dut.irq), 1)
            yield

            # deactivate ev_0, clear ev_pending, check that IRQ line goes low
            yield dut.ev_0.stb.eq(0)
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.w_data.eq(0b001)
            yield dut.csr_bus.w_stb.eq(1)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 0)

            # activate ev_1, check that ev_1 is pending, and IRQ line goes high
            yield dut.ev_1.stb.eq(1)
            yield
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0b010)
            self.assertEqual((yield dut.irq), 1)

            # clear ev_pending, check that IRQ line goes low
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.w_data.eq(0b010)
            yield dut.csr_bus.w_stb.eq(1)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 0)

            # deactivate ev_2, check that ev_2 is pending, and IRQ line goes high
            yield dut.ev_2.stb.eq(0)
            yield
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0b100)
            self.assertEqual((yield dut.irq), 1)

            # clear ev_pending, check that IRQ line goes low
            yield dut.csr_bus.addr.eq(ev_pending_addr)
            yield dut.csr_bus.w_data.eq(0b100)
            yield dut.csr_bus.w_stb.eq(1)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 0)

        simulation_test(dut, process)
