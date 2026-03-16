from amaranth import *

from ..memory import MemoryMap

class Interface(Record):
    """SRAM interface.

    A low-level interface for accessing SRAM blocks.

    Parameters
    ----------
    addr_width : int
        Address width. At most ``(2 ** addr_width) * data_width`` bits of memory will be available.
    data_width : int
        Data width. Word size of the SRAM block.
    words : int
        The number of words of :arg:`data_width` bits in the SRAM block. This allows to have an
        SRAM block not covering the full address space provided by :arg:`addr_width`. Only values
        are allowed where MSB of the address is used given the condition of
        ``2**(addr_width - 1) < words <= 2**addr_width``.
        If no value is specified the full ``2**addr_width`` is used.
    name : str
        Name of the underlying record.

    Attributes
    ----------
    memory_map : MemoryMap
        The memory map of the SRAM block; determined by the :arg:`words` and arg:`data_width`
        arguments.
    a : Signal(addr_width)
        Address for reads and writes
    d_r : Signal(data_width)
        Read data. The SRAM interface is defined asynchronous and no guarantees are made on
        timing for availability of the data.
    d_w : Signal(data_width)
        Write data. The SRAM interface is defined asynchronous and does not define timing
        requirement of d_w and we.
    we : Signal()
        Enable write. The SRAM interface is defined asynchronous and does not define timing
        requirement of d_w and we.
    ce : Signal()
        Enable SRAM block interface.
    """

    def __init__(self, *, addr_width, data_width, words=None, name=None):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise ValueError(
                "Address width must be a positive integer, not {!r}".format(addr_width)
            )
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError(
                "Data width must be a positive integer, not {!r}".format(data_width)
            )
        if words is None:
            words = 2**addr_width
        if not isinstance(words, int) or not (2**(addr_width - 1) < words <= 2**addr_width):
            raise ValueError(
                "# words has to integer between 2**(addr_width-1) and 2**addr_width, not {!r}"
                .format(words),
            )
        self.addr_width = addr_width
        self.data_width = data_width
        self.words = words
        self._map = memmap = MemoryMap(addr_width=addr_width, data_width=data_width)

        super().__init__([
            ("a", addr_width),
            ("d_r", data_width),
            ("d_w", data_width),
            ("we", 1),
            ("ce", 1),
        ], name=name, src_loc_at=1)

        memmap.add_resource(self, name=(name if name is not None else "sram"), size=words)
        memmap.freeze()

    @property
    def memory_map(self):
        return self._map

    def __hash__(self):
        """Each object represents a different SRAM block"""
        return id(self)
