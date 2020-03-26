from nmigen import *
from nmigen.utils import log2_int

from . import Interface as CSRInterface
from ..wishbone import Interface as WishboneInterface
from ..memory import MemoryMap


__all__ = ["WishboneCSRBridge"]


class WishboneCSRBridge(Elaboratable):
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
    data_width : int or None
        Wishbone bus data width. If not specified, defaults to ``csr_bus.data_width``.

    Attributes
    ----------
    wb_bus : :class:`..wishbone.Interface`
        Wishbone bus provided by the bridge.
    """
    def __init__(self, csr_bus, *, data_width=None):
        if not isinstance(csr_bus, CSRInterface):
            raise ValueError("CSR bus must be an instance of CSRInterface, not {!r}"
                             .format(csr_bus))
        if csr_bus.data_width not in (8, 16, 32, 64):
            raise ValueError("CSR bus data width must be one of 8, 16, 32, 64, not {!r}"
                             .format(csr_bus.data_width))
        if data_width is None:
            data_width = csr_bus.data_width

        self.csr_bus = csr_bus
        self.wb_bus  = WishboneInterface(
            addr_width=max(0, csr_bus.addr_width - log2_int(data_width // csr_bus.data_width)),
            data_width=data_width,
            granularity=csr_bus.data_width,
            name="wb")

        self.wb_bus.memory_map = MemoryMap(addr_width=csr_bus.addr_width,
                                           data_width=csr_bus.data_width)

        # Since granularity of the Wishbone interface matches the data width of the CSR bus,
        # no width conversion is performed, even if the Wishbone data width is greater.
        self.wb_bus.memory_map.add_window(self.csr_bus.memory_map)

    def elaborate(self, platform):
        csr_bus = self.csr_bus
        wb_bus  = self.wb_bus

        m = Module()

        cycle = Signal(range(len(wb_bus.sel) + 1))
        m.d.comb += csr_bus.addr.eq(Cat(cycle[:log2_int(len(wb_bus.sel))], wb_bus.adr))

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

        with m.Else():
            m.d.sync += wb_bus.ack.eq(0)

        with m.If(wb_bus.ack):
            m.d.sync += cycle.eq(0)

        return m
