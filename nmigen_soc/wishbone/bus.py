from enum import Enum
from nmigen import *
from nmigen.hdl.rec import Direction
from nmigen.utils import log2_int

from ..memory import MemoryMap


__all__ = ["CycleType", "BurstTypeExt", "Interface"]


class CycleType(Enum):
    """Wishbone Registered Feedback cycle type."""
    CLASSIC      = 0b000
    CONST_BURST  = 0b001
    INCR_BURST   = 0b010
    END_OF_BURST = 0b111


class BurstTypeExt(Enum):
    """Wishbone Registered Feedback burst type extension."""
    LINEAR  = 0b00
    WRAP_4  = 0b01
    WRAP_8  = 0b10
    WRAP_16 = 0b11


class Interface(Record):
    """Wishbone interface.

    See the `Wishbone specification <https://opencores.org/howto/wishbone>`_ for description
    of the Wishbone signals. The ``RST_I`` and ``CLK_I`` signals are provided as a part of
    the clock domain that drives the interface.

    Note that the data width of the underlying memory map of the interface is equal to port
    granularity, not port size. If port granularity is less than port size, then the address width
    of the underlying memory map is extended to reflect that.

    Parameters
    ----------
    addr_width : int
        Width of the address signal.
    data_width : int
        Width of the data signals ("port size" in Wishbone terminology).
        One of 8, 16, 32, 64.
    granularity : int
        Granularity of select signals ("port granularity" in Wishbone terminology).
        One of 8, 16, 32, 64.
    optional : iter(str)
        Selects the optional signals that will be a part of this interface.
    alignment : int
        Resource and window alignment. See :class:`MemoryMap`.
    name : str
        Name of the underlying record.

    Attributes
    ----------
    The correspondence between the nMigen-SoC signals and the Wishbone signals changes depending
    on whether the interface acts as an initiator or a target.

    adr : Signal(addr_width)
        Corresponds to Wishbone signal ``ADR_O`` (initiator) or ``ADR_I`` (target).
    dat_w : Signal(data_width)
        Corresponds to Wishbone signal ``DAT_O`` (initiator) or ``DAT_I`` (target).
    dat_r : Signal(data_width)
        Corresponds to Wishbone signal ``DAT_I`` (initiator) or ``DAT_O`` (target).
    sel : Signal(data_width // granularity)
        Corresponds to Wishbone signal ``SEL_O`` (initiator) or ``SEL_I`` (target).
    cyc : Signal()
        Corresponds to Wishbone signal ``CYC_O`` (initiator) or ``CYC_I`` (target).
    stb : Signal()
        Corresponds to Wishbone signal ``STB_O`` (initiator) or ``STB_I`` (target).
    we : Signal()
        Corresponds to Wishbone signal ``WE_O``  (initiator) or ``WE_I``  (target).
    ack : Signal()
        Corresponds to Wishbone signal ``ACK_I`` (initiator) or ``ACK_O`` (target).
    err : Signal()
        Optional. Corresponds to Wishbone signal ``ERR_I`` (initiator) or ``ERR_O`` (target).
    rty : Signal()
        Optional. Corresponds to Wishbone signal ``RTY_I`` (initiator) or ``RTY_O`` (target).
    stall : Signal()
        Optional. Corresponds to Wishbone signal ``STALL_I`` (initiator) or ``STALL_O`` (target).
    lock : Signal()
        Optional. Corresponds to Wishbone signal ``LOCK_O`` (initiator) or ``LOCK_I`` (target).
    cti : Signal()
        Optional. Corresponds to Wishbone signal ``CTI_O`` (initiator) or ``CTI_I`` (target).
    bte : Signal()
        Optional. Corresponds to Wishbone signal ``BTE_O`` (initiator) or ``BTE_I`` (target).
    """
    def __init__(self, *, addr_width, data_width, granularity=None, optional=frozenset(),
                 alignment=0, name=None):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise ValueError("Address width must be a non-negative integer, not {!r}"
                             .format(addr_width))
        if data_width not in (8, 16, 32, 64):
            raise ValueError("Data width must be one of 8, 16, 32, 64, not {!r}"
                             .format(data_width))
        if granularity is None:
            granularity = data_width
        elif granularity not in (8, 16, 32, 64):
            raise ValueError("Granularity must be one of 8, 16, 32, 64, not {!r}"
                             .format(granularity))
        if granularity > data_width:
            raise ValueError("Granularity {} may not be greater than data width {}"
                             .format(granularity, data_width))
        self.addr_width  = addr_width
        self.data_width  = data_width
        self.granularity = granularity
        granularity_bits = log2_int(data_width // granularity)
        self.memory_map  = MemoryMap(addr_width=max(1, addr_width + granularity_bits),
                                     data_width=data_width >> granularity_bits,
                                     alignment=alignment)

        optional = set(optional)
        unknown  = optional - {"rty", "err", "stall", "lock", "cti", "bte"}
        if unknown:
            raise ValueError("Optional signal(s) {} are not supported"
                             .format(", ".join(map(repr, unknown))))
        layout = [
            ("adr",   addr_width, Direction.FANOUT),
            ("dat_w", data_width, Direction.FANOUT),
            ("dat_r", data_width, Direction.FANIN),
            ("sel",   data_width // granularity, Direction.FANOUT),
            ("cyc",   1, Direction.FANOUT),
            ("stb",   1, Direction.FANOUT),
            ("we",    1, Direction.FANOUT),
            ("ack",   1, Direction.FANIN),
        ]
        if "err" in optional:
            layout += [("err", 1, Direction.FANIN)]
        if "rty" in optional:
            layout += [("rty", 1, Direction.FANIN)]
        if "stall" in optional:
            layout += [("stall", 1, Direction.FANIN)]
        if "lock" in optional:
            layout += [("lock",  1, Direction.FANOUT)]
        if "cti" in optional:
            layout += [("cti", CycleType,    Direction.FANOUT)]
        if "bte" in optional:
            layout += [("bte", BurstTypeExt, Direction.FANOUT)]
        super().__init__(layout, name=name, src_loc_at=1)
