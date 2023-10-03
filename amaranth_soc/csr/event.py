# amaranth: UnusedElaboratable=no
from math import ceil

from amaranth import *
from amaranth.utils import log2_int

from . import Element, Multiplexer
from .. import event


__all__ = ["EventMonitor"]


class EventMonitor(Elaboratable):
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
    name : str
        Window name. Optional. See :class:`..memory.MemoryMap`.
    """
    def __init__(self, event_map, *, trigger="level", data_width, alignment=0, name=None):
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError(f"Data width must be a positive integer, not {data_width!r}")
        if not isinstance(alignment, int) or alignment < 0:
            raise ValueError(f"Alignment must be a non-negative integer, not {alignment!r}")

        self._monitor = event.Monitor(event_map, trigger=trigger)
        self._enable  = Element(event_map.size, "rw", path=("enable",))
        self._pending = Element(event_map.size, "rw", path=("pending",))

        elem_size  = ceil(event_map.size / data_width)
        addr_width = 1 + max(log2_int(elem_size, need_pow2=False), alignment)
        self._mux  = Multiplexer(addr_width=addr_width, data_width=data_width,
                                 alignment=alignment, name=name)
        self._mux.add(self._enable,  name="enable")
        self._mux.add(self._pending, name="pending")

    @property
    def src(self):
        """Event source.

        Return value
        ------------
        An :class:`..event.Source`. Its input line is asserted by the monitor when a subordinate
        event is enabled and pending.
        """
        return self._monitor.src

    @property
    def bus(self):
        """CSR bus interface.

        Return value
        ------------
        A :class:`..csr.Interface` providing access to registers.
        """
        return self._mux.bus

    def elaborate(self, platform):
        m = Module()
        m.submodules.monitor = self._monitor
        m.submodules.mux     = self._mux

        with m.If(self._enable.w_stb):
            m.d.sync += self._monitor.enable.eq(self._enable.w_data)
        m.d.comb += self._enable.r_data.eq(self._monitor.enable)

        with m.If(self._pending.w_stb):
            m.d.comb += self._monitor.clear.eq(self._pending.w_data)
        m.d.comb += self._pending.r_data.eq(self._monitor.pending)

        return m
