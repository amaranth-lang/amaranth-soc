from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In
from amaranth.lib.memory import MemoryData, Memory
from amaranth.utils import exact_log2

from ..memory import MemoryMap
from .bus import Signature


__all__ = ["WishboneSRAM"]


class WishboneSRAM(wiring.Component):
    """Wishbone-attached SRAM.

    Wishbone bus accesses have a latency of one clock cycle.

    Arguments
    ---------
    size : :class:`int`, power of two
        SRAM size, in units of ``granularity`` bits.
    data_width : ``8``, ``16``, ``32`` or ``64``
        Wishbone bus data width.
    granularity : ``8``, ``16``, ``32`` or ``64``, optional
        Wishbone bus granularity. If unspecified, it defaults to ``data_width``.
    writable : bool
        Write capability. If disabled, writes are ignored. Enabled by default.
    init : iterable of initial values, optional
        Initial values for memory rows. There are ``(size * granularity) // data_width`` rows,
        and each row has a shape of ``unsigned(data_width)``.

    Members
    -------
    wb_bus : ``In(wishbone.Signature(...))``
        Wishbone bus interface.

    Raises
    ------
    :exc:`ValueError`
        If ``size * granularity`` is lesser than ``data_width``.
    """
    def __init__(self, *, size, data_width, granularity=None, writable=True, init=()):
        if granularity is None:
            granularity = data_width

        if not isinstance(size, int) or size <= 0 or size & size-1:
            raise TypeError(f"Size must be an integer power of two, not {size!r}")
        if data_width not in (8, 16, 32, 64):
            raise TypeError(f"Data width must be 8, 16, 32 or 64, not {data_width!r}")
        if granularity not in (8, 16, 32, 64):
            raise TypeError(f"Granularity must be 8, 16, 32 or 64, not {granularity!r}")
        if size * granularity < data_width:
            raise ValueError(f"The product of size {size} and granularity {granularity} must be "
                             f"greater than or equal to data width {data_width}, not "
                             f"{size * granularity}")

        self._size     = size
        self._writable = bool(writable)
        self._mem_data = MemoryData(depth=(size * granularity) // data_width,
                                    shape=unsigned(data_width), init=init)
        self._mem      = Memory(self._mem_data)

        super().__init__({"wb_bus": In(Signature(addr_width=exact_log2(self._mem.depth),
                                                 data_width=data_width, granularity=granularity))})

        self.wb_bus.memory_map = MemoryMap(addr_width=exact_log2(size), data_width=granularity)
        self.wb_bus.memory_map.add_resource(self._mem, name=("mem",), size=size)
        self.wb_bus.memory_map.freeze()

    @property
    def size(self):
        return self._size

    @property
    def writable(self):
        return self._writable

    @property
    def init(self):
        return self._mem_data.init

    @init.setter
    def init(self, init):
        self._mem_data.init = init

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self._mem

        read_port = self._mem.read_port()
        m.d.comb += [
            read_port.addr.eq(self.wb_bus.adr),
            self.wb_bus.dat_r.eq(read_port.data),
        ]

        if self.writable:
            write_port = self._mem.write_port(granularity=self.wb_bus.granularity)
            m.d.comb += [
                write_port.addr.eq(self.wb_bus.adr),
                write_port.data.eq(self.wb_bus.dat_w),
            ]

        with m.If(self.wb_bus.ack):
            m.d.sync += self.wb_bus.ack.eq(0)
        with m.Elif(self.wb_bus.cyc & self.wb_bus.stb):
            if self.writable:
                m.d.comb += write_port.en.eq(Mux(self.wb_bus.we, self.wb_bus.sel, 0))
                m.d.comb += read_port.en.eq(~self.wb_bus.we)
            m.d.sync += self.wb_bus.ack.eq(1)

        return m
