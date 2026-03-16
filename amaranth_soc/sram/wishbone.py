from amaranth import *
from amaranth.utils import log2_int

from .bus import Interface
from .. import wishbone as wb, memory as mem


__all__ = ["WishboneSRAMBridge"]


class WishboneSRAMBridge(Elaboratable):
    """Wishbone to SRAM bridge.

    A bus bridge for accessing SRAM blocks from Wishbone. This bridge drives one or more
    SRAM blocks from the Wishbone interface. The data width of the individual blocks
    determines the granularity of the Wishbone interface and the number of interfaces the
    data_width. A dynamic configurable number wait states can be inserted in each
    Wishbone bus operation.

    Parameters
    ----------
    sram_buses : :class:`..sram.Interface` or iterable of :class:`..sram.Interface`
        SRAM buses driven by the bridge. All buses need to have same address and data
        widths.
    wait_states : :class:Signal or :class:Const
        The number of wait states to insert before acknowledging a cycle. This value is
        not latched at the beginning of a cycle so should normally be kept stable during
        a bus cycle.
    
    Attributes
    ----------
    wb_bus : :class:`..wishbone.Interface`
        Wishbone bus provided by the bridge.
    """
    def __init__(self, sram_buses, *, wait_states=Const(0, 1), name="wb"):
        if isinstance(sram_buses, Interface):
            sram_buses = [sram_buses]
        else:
            try:
                for sram_bus in sram_buses:
                    assert isinstance(sram_bus, Interface)
            except:
                raise ValueError(
                    "SRAM buses has to be an iterable of sram.Interface, not {!r}".format(sram_buses)
                )
        # Support len(sram_buses) and make sram_buses hashable
        sram_buses = tuple(sram_buses)
        n_rams = len(sram_buses)
        addr_width = sram_buses[0].addr_width
        granularity = sram_buses[0].data_width
        words = sram_buses[0].words
        for sram_bus in sram_buses[1:]:
            if sram_bus.addr_width != addr_width:
                raise ValueError("All SRAMs have to have the same address width")
            if sram_bus.data_width != granularity:
                raise ValueError("All SRAMs have to have the same data width")
            if sram_bus.words != words:
                raise ValueError("All SRAMs have to have the same number of words")
        data_width = granularity*len(sram_buses)

        self.sram_buses = sram_buses
        self.wait_states = wait_states
        self.wb_bus = wb_bus = wb.Interface(
            addr_width=addr_width,
            data_width=data_width,
            granularity=granularity,
            name=name,
        )
        if n_rams == 1:
            wb_bus.memory_map = sram_buses[0].memory_map
        else:
            size = words*len(sram_buses)
            map_addr_width = log2_int(size, need_pow2=False)
            memmap = mem.MemoryMap(addr_width=map_addr_width, data_width=granularity)
            memmap.add_resource(sram_buses, name=name, size=size)
            wb_bus.memory_map = memmap

    def elaborate(self, platform):
        sram_buses = self.sram_buses
        wait_states = self.wait_states
        wb_bus = self.wb_bus

        m = Module()

        wb_cycle = Signal()
        m.d.comb += wb_cycle.eq(wb_bus.cyc & wb_bus.stb)

        for i, sram_bus in enumerate(sram_buses):
            s = slice(i*wb_bus.granularity, (i+1)*wb_bus.granularity)
            m.d.comb += [
                sram_bus.a.eq(wb_bus.adr),
                sram_bus.ce.eq(wb_cycle & wb_bus.sel[i]),
                sram_bus.we.eq(wb_cycle & wb_bus.sel[i] & wb_bus.we),
                wb_bus.dat_r[s].eq(sram_bus.d_r),
                sram_bus.d_w.eq(wb_bus.dat_w[s]),
            ]

        waitcnt = Signal(len(wait_states))
        with m.If(wb_cycle):
            with m.If(waitcnt != wait_states):
                m.d.comb += wb_bus.ack.eq(0)
                m.d.sync += waitcnt.eq(waitcnt + 1)
            with m.Else():
                m.d.comb += wb_bus.ack.eq(1)
                m.d.sync += waitcnt.eq(0)
        with m.Else():
            m.d.comb += wb_bus.ack.eq(0)
            m.d.sync += waitcnt.eq(0)

        return m
