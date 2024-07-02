from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, flipped
from amaranth.utils import exact_log2

from . import Interface
from .. import wishbone
from ..memory import MemoryMap


__all__ = ["WishboneCSRBridge"]


class WishboneCSRBridge(wiring.Component):
    """Wishbone to CSR bridge.

    A bus bridge for accessing CSR registers from Wishbone. This bridge supports any Wishbone
    data width greater or equal to CSR data width and performs appropriate address translation.

    Latency
    -------

    Reads and writes always take ``self.data_width // csr_bus.data_width + 1`` cycles to complete,
    regardless of the select inputs. Write side effects occur simultaneously with acknowledgement.

    Parameters
    ----------
    csr_bus : :class:`..csr.Interface`
        CSR bus driven by the bridge.
    data_width : int
        Wishbone bus data width. Optional. If ``None``, defaults to ``csr_bus.data_width``.
    name : :class:`..memory.MemoryMap.Name`
        Window name. Optional.

    Attributes
    ----------
    wb_bus : :class:`..wishbone.Interface`
        Wishbone bus provided by the bridge.
    """
    def __init__(self, csr_bus, *, data_width=None, name=None):
        if isinstance(csr_bus, wiring.FlippedInterface):
            csr_bus_unflipped = flipped(csr_bus)
        else:
            csr_bus_unflipped = csr_bus
        if not isinstance(csr_bus_unflipped, Interface):
            raise TypeError(f"CSR bus must be an instance of csr.Interface, not "
                            f"{csr_bus_unflipped!r}")
        if csr_bus.data_width not in (8, 16, 32, 64):
            raise ValueError(f"CSR bus data width must be one of 8, 16, 32, 64, not "
                             f"{csr_bus.data_width!r}")
        if data_width is None:
            data_width = csr_bus.data_width

        ratio  = data_width // csr_bus.data_width
        wb_sig = wishbone.Signature(addr_width=max(0, csr_bus.addr_width - exact_log2(ratio)),
                                    data_width=data_width,
                                    granularity=csr_bus.data_width)

        super().__init__({"wb_bus": In(wb_sig)})

        self.wb_bus.memory_map = MemoryMap(addr_width=csr_bus.addr_width,
                                           data_width=csr_bus.data_width)
        # Since granularity of the Wishbone interface matches the data width of the CSR bus,
        # no width conversion is performed, even if the Wishbone data width is greater.
        self.wb_bus.memory_map.add_window(csr_bus.memory_map, name=name)

        self._csr_bus = csr_bus

    @property
    def csr_bus(self):
        return self._csr_bus

    def elaborate(self, platform):
        csr_bus = self.csr_bus
        wb_bus  = self.wb_bus

        m = Module()

        cycle = Signal(range(len(wb_bus.sel) + 1))
        m.d.comb += csr_bus.addr.eq(Cat(cycle[:exact_log2(len(wb_bus.sel))], wb_bus.adr))

        with m.If(wb_bus.cyc & wb_bus.stb):
            with m.Switch(cycle):
                def segment(index):
                    return slice(index * wb_bus.granularity, (index + 1) * wb_bus.granularity)

                for index, sel_index in enumerate(wb_bus.sel):
                    with m.Case(index):
                        if index > 0:
                            # CSR reads are registered, and we need to re-register them.
                            m.d.sync += wb_bus.dat_r[segment(index - 1)].eq(csr_bus.r_data)
                        m.d.comb += csr_bus.r_stb.eq(sel_index & ~wb_bus.we)
                        m.d.comb += csr_bus.w_data.eq(wb_bus.dat_w[segment(index)])
                        m.d.comb += csr_bus.w_stb.eq(sel_index & wb_bus.we)
                        m.d.sync += cycle.eq(index + 1)

                with m.Default():
                    m.d.sync += wb_bus.dat_r[segment(index)].eq(csr_bus.r_data)
                    m.d.sync += wb_bus.ack.eq(1)

        with m.If(wb_bus.ack):
            m.d.sync += cycle.eq(0)
            m.d.sync += wb_bus.ack.eq(0)

        return m
