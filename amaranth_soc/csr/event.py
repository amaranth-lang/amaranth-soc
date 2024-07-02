# amaranth: UnusedElaboratable=no
from math import ceil

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, flipped, connect
from amaranth.utils import ceil_log2

from . import Multiplexer
from .reg import Register, Field, FieldAction
from .. import event
from ..memory import MemoryMap


__all__ = ["EventMonitor"]


class _EventMaskRegister(Register, access="rw"):
    def __init__(self, width):
        super().__init__({"mask": Field(FieldAction, width, access="rw")})


class EventMonitor(wiring.Component):
    """Event monitor.

    A monitor for subordinate event sources, with a CSR bus interface.

    CSR registers
    -------------
    enable : ``event_map.size``, read/write
        Enabled events. See :meth:`..event.EventMap.sources` for layout.
    pending : ``event_map.size``, read/clear
        Pending events. See :meth:`..event.EventMap.sources` for layout.

    Parameters
    ----------
    event_map : :class:`..event.EventMap`
        A collection of event sources.
    trigger : :class:`..event.Source.Trigger`
        Trigger mode. See :class:`..event.Source`.
    data_width : int
        CSR bus data width. See :class:`..csr.Interface`.
    alignment : int, power-of-2 exponent
        CSR address alignment. See :class:`..memory.MemoryMap`.

    Attributes
    ----------
    src : :class:`..event.Source`
        Event source. Its input line is asserted by the monitor when a subordinate event is enabled
        and pending.
    bus : :class:`..csr.Interface`
        CSR bus interface.
    """
    def __init__(self, event_map, *, trigger="level", data_width, alignment=0, name=None):
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError(f"Data width must be a positive integer, not {data_width!r}")
        if not isinstance(alignment, int) or alignment < 0:
            raise ValueError(f"Alignment must be a non-negative integer, not {alignment!r}")

        self._monitor = event.Monitor(event_map, trigger=trigger)
        self._enable  = _EventMaskRegister(event_map.size)
        self._pending = _EventMaskRegister(event_map.size)

        reg_size   = (event_map.size + data_width - 1) // data_width
        addr_width = 1 + max(ceil_log2(reg_size), alignment)
        memory_map = MemoryMap(addr_width=addr_width, data_width=data_width, alignment=alignment)
        memory_map.add_resource(self._enable,  size=reg_size, name=("enable",))
        memory_map.add_resource(self._pending, size=reg_size, name=("pending",))

        self._mux = Multiplexer(memory_map)

        super().__init__({
            "src": Out(self._monitor.src.signature),
            "bus": In(self._mux.bus.signature),
        })
        self.bus.memory_map = self._mux.bus.memory_map

    def elaborate(self, platform):
        m = Module()
        m.submodules.monitor = self._monitor
        m.submodules.mux     = self._mux

        connect(m, flipped(self.src), self._monitor.src)
        connect(m, self.bus, self._mux.bus)

        with m.If(self._enable.element.w_stb):
            m.d.sync += self._monitor.enable.eq(self._enable.element.w_data)
        m.d.comb += self._enable.element.r_data.eq(self._monitor.enable)

        with m.If(self._pending.element.w_stb):
            m.d.comb += self._monitor.clear.eq(self._pending.element.w_data)
        m.d.comb += self._pending.element.r_data.eq(self._monitor.pending)

        return m
