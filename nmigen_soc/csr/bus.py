import enum
from nmigen import *
from nmigen.utils import log2_int

from ..memory import MemoryMap


__all__ = ["Element", "Interface", "Decoder", "Multiplexer"]


class Element(Record):
    class Access(enum.Enum):
        """Register access mode.

        Coarse access mode for the entire register. Individual fields can have more restrictive
        access mode, e.g. R/O fields can be a part of an R/W register.
        """
        R  = "r"
        W  = "w"
        RW = "rw"

        def readable(self):
            return self == self.R or self == self.RW

        def writable(self):
            return self == self.W or self == self.RW

    """Peripheral-side CSR interface.

    A low-level interface to a single atomically readable and writable register in a peripheral.
    This interface supports any register width and semantics, provided that both reads and writes
    always succeed and complete in one cycle.

    Parameters
    ----------
    width : int
        Width of the register.
    access : :class:`Access`
        Register access mode.
    name : str
        Name of the underlying record.

    Attributes
    ----------
    r_data : Signal(width)
        Read data. Must be always valid, and is sampled when ``r_stb`` is asserted.
    r_stb : Signal()
        Read strobe. Registers with read side effects should perform the read side effect when this
        strobe is asserted.
    w_data : Signal(width)
        Write data. Valid only when ``w_stb`` is asserted.
    w_stb : Signal()
        Write strobe. Registers should update their value or perform the write side effect when
        this strobe is asserted.
    """
    def __init__(self, width, access, *, name=None, src_loc_at=0):
        if not isinstance(width, int) or width < 0:
            raise ValueError("Width must be a non-negative integer, not {!r}"
                             .format(width))
        if not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        self.width  = width
        self.access = Element.Access(access)

        layout = []
        if self.access.readable():
            layout += [
                ("r_data", width),
                ("r_stb",  1),
            ]
        if self.access.writable():
            layout += [
                ("w_data", width),
                ("w_stb",  1),
            ]
        super().__init__(layout, name=name, src_loc_at=1 + src_loc_at)

    # FIXME: get rid of this
    __hash__ = object.__hash__


class Interface(Record):
    """CPU-side CSR interface.

    A low-level interface to a set of atomically readable and writable peripheral CSR registers.

    Operation
    ---------

    CSR registers mapped to the CSR bus are split into chunks according to the bus data width.
    Each chunk is assigned a consecutive address on the bus. This allows accessing CSRs of any
    size using any datapath width.

    When the first chunk of a register is read, the value of a register is captured, and reads
    from subsequent chunks of the same register return the captured values. When any chunk except
    the last chunk of a register is written, the written value is captured; a write to the last
    chunk writes the captured value to the register. This allows atomically accessing CSRs larger
    than datapath width.

    Parameters
    ----------
    addr_width : int
        Address width. At most ``(2 ** addr_width) * data_width`` register bits will be available.
    data_width : int
        Data width. Registers are accessed in ``data_width`` sized chunks.
    name : str
        Name of the underlying record.

    Attributes
    ----------
    memory_map : MemoryMap
        Map of the bus.
    addr : Signal(addr_width)
        Address for reads and writes.
    r_data : Signal(data_width)
        Read data. Valid on the next cycle after ``r_stb`` is asserted. Otherwise, zero. (Keeping
        read data of an unused interface at zero simplifies multiplexers.)
    r_stb : Signal()
        Read strobe. If ``addr`` points to the first chunk of a register, captures register value
        and causes read side effects to be performed (if any). If ``addr`` points to any chunk
        of a register, latches the captured value to ``r_data``. Otherwise, latches zero
        to ``r_data``.
    w_data : Signal(data_width)
        Write data. Must be valid when ``w_stb`` is asserted.
    w_stb : Signal()
        Write strobe. If ``addr`` points to the last chunk of a register, writes captured value
        to the register and causes write side effects to be performed (if any). If ``addr`` points
        to any chunk of a register, latches ``w_data`` to the captured value. Otherwise, does
        nothing.
    """

    def __init__(self, *, addr_width, data_width, name=None):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise ValueError("Address width must be a positive integer, not {!r}"
                             .format(addr_width))
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError("Data width must be a positive integer, not {!r}"
                             .format(data_width))
        self.addr_width = addr_width
        self.data_width = data_width
        self._map       = None

        super().__init__([
            ("addr",    addr_width),
            ("r_data",  data_width),
            ("r_stb",   1),
            ("w_data",  data_width),
            ("w_stb",   1),
        ], name=name, src_loc_at=1)

    @property
    def memory_map(self):
        if self._map is None:
            raise NotImplementedError("Bus interface {!r} does not have a memory map"
                                      .format(self))
        return self._map

    @memory_map.setter
    def memory_map(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError("Memory map must be an instance of MemoryMap, not {!r}"
                            .format(memory_map))
        if memory_map.addr_width != self.addr_width:
            raise ValueError("Memory map has address width {}, which is not the same as "
                             "bus interface address width {}"
                             .format(memory_map.addr_width, self.addr_width))
        if memory_map.data_width != self.data_width:
            raise ValueError("Memory map has data width {}, which is not the same as "
                             "bus interface data width {}"
                             .format(memory_map.data_width, self.data_width))
        memory_map.freeze()
        self._map = memory_map


class Multiplexer(Elaboratable):
    """CSR register multiplexer.

    An address-based multiplexer for CSR registers implementing atomic updates.

    Latency
    -------

    Writes are registered, and are performed 1 cycle after ``w_stb`` is asserted.

    Alignment
    ---------

    Because the CSR bus conserves logic and routing resources, it is common to e.g. access
    a CSR bus with an *n*-bit data path from a CPU with a *k*-bit datapath (*k>n*) in cases
    where CSR access latency is less important than resource usage. In this case, two strategies
    are possible for connecting the CSR bus to the CPU:
        * The CPU could access the CSR bus directly (with no intervening logic other than simple
          translation of control signals). In this case, the register alignment should be set
          to 1, and each *w*-bit register would occupy *ceil(w/n)* addresses from the CPU
          perspective, requiring the same amount of memory instructions to access.
        * The CPU could also access the CSR bus through a width down-converter, which would issue
          *k/n* CSR accesses for each CPU access. In this case, the register alignment should be
          set to *k/n*, and each *w*-bit register would occupy *ceil(w/k)* addresses from the CPU
          perspective, requiring the same amount of memory instructions to access.

    If alignment is greater than 1, it affects which CSR bus write is considered a write to
    the last register chunk. For example, if a 24-bit register is used with a 8-bit CSR bus and
    a CPU with a 32-bit datapath, a write to this register requires 4 CSR bus writes to complete
    and the 4th write is the one that actually writes the value to the register. This allows
    determining write latency solely from the amount of addresses the register occupies in
    the CPU address space, and the width of the CSR bus.

    Parameters
    ----------
    addr_width : int
        Address width. See :class:`Interface`.
    data_width : int
        Data width. See :class:`Interface`.
    alignment : int
        Register alignment. See :class:`Interface`.

    Attributes
    ----------
    bus : :class:`Interface`
        CSR bus providing access to registers.
    """
    def __init__(self, *, addr_width, data_width, alignment=0):
        self._map = MemoryMap(addr_width=addr_width, data_width=data_width, alignment=alignment)
        self._bus = None

    @property
    def bus(self):
        if self._bus is None:
            self._map.freeze()
            self._bus = Interface(addr_width=self._map.addr_width,
                                  data_width=self._map.data_width,
                                  name="csr")
            self._bus.memory_map = self._map
        return self._bus

    def align_to(self, alignment):
        """Align the implicit address of the next register.

        See :meth:`MemoryMap.align_to` for details.
        """
        return self._map.align_to(alignment)

    def add(self, element, *, addr=None, alignment=None, extend=False):
        """Add a register.

        See :meth:`MemoryMap.add_resource` for details.
        """
        if not isinstance(element, Element):
            raise TypeError("Element must be an instance of csr.Element, not {!r}"
                            .format(element))

        size = (element.width + self._map.data_width - 1) // self._map.data_width
        return self._map.add_resource(element, size=size, addr=addr, alignment=alignment,
                                      extend=extend)

    def elaborate(self, platform):
        m = Module()

        # Instead of a straightforward multiplexer for reads, use a per-element address comparator,
        # AND the shadow register chunk with the comparator output, and OR all of those together.
        # If the toolchain doesn't already synthesize multiplexer trees this way, this trick can
        # save a significant amount of logic, since e.g. one 4-LUT can pack one 2-MUX, but two
        # 2-AND or 2-OR gates.
        r_data_fanin = 0

        for elem, (elem_start, elem_end) in self._map.resources():
            shadow = Signal(elem.width, name="{}__shadow".format(elem.name))
            if elem.access.readable():
                shadow_en = Signal(elem_end - elem_start, name="{}__shadow_en".format(elem.name))
                m.d.sync += shadow_en.eq(0)
            if elem.access.writable():
                m.d.comb += elem.w_data.eq(shadow)
                m.d.sync += elem.w_stb.eq(0)

            # Enumerate every address used by the register explicitly, rather than using
            # arithmetic comparisons, since some toolchains (e.g. Yosys) are too eager to infer
            # carry chains for comparisons, even with a constant. (Register sizes don't have
            # to be powers of 2.)
            with m.Switch(self.bus.addr):
                for chunk_offset, chunk_addr in enumerate(range(elem_start, elem_end)):
                    shadow_slice = shadow.word_select(chunk_offset, self.bus.data_width)

                    with m.Case(chunk_addr):
                        if elem.access.readable():
                            r_data_fanin |= Mux(shadow_en[chunk_offset], shadow_slice, 0)
                            if chunk_addr == elem_start:
                                m.d.comb += elem.r_stb.eq(self.bus.r_stb)
                                with m.If(self.bus.r_stb):
                                    m.d.sync += shadow.eq(elem.r_data)
                            # Delay by 1 cycle, allowing reads to be pipelined.
                            m.d.sync += shadow_en.eq(self.bus.r_stb << chunk_offset)

                        if elem.access.writable():
                            if chunk_addr == elem_end - 1:
                                # Delay by 1 cycle, avoiding combinatorial paths through
                                # the CSR bus and into CSR registers.
                                m.d.sync += elem.w_stb.eq(self.bus.w_stb)
                            with m.If(self.bus.w_stb):
                                m.d.sync += shadow_slice.eq(self.bus.w_data)

        m.d.comb += self.bus.r_data.eq(r_data_fanin)

        return m


class Decoder(Elaboratable):
    """CSR bus decoder.

    An address decoder for subordinate CSR buses.

    Usage
    -----

    Although there is no functional difference between adding a set of registers directly to
    a :class:`Multiplexer` and adding a set of registers to multiple :class:`Multiplexer`s that are
    aggregated with a :class:`Decoder`, hierarchical CSR buses are useful for organizing
    a hierarchical design. If many peripherals are directly served by a single
    :class:`Multiplexer`, a very large amount of ports will connect the peripheral registers with
    the decoder, and the cost of decoding logic would not be attributed to specific peripherals.
    With a decoder, only five signals per peripheral will be used, and the logic could be kept
    together with the peripheral.

    Parameters
    ----------
    addr_width : int
        Address width. See :class:`Interface`.
    data_width : int
        Data width. See :class:`Interface`.
    alignment : int
        Window alignment. See :class:`Interface`.

    Attributes
    ----------
    bus : :class:`Interface`
        CSR bus providing access to subordinate buses.
    """
    def __init__(self, *, addr_width, data_width, alignment=0):
        self._map  = MemoryMap(addr_width=addr_width, data_width=data_width, alignment=alignment)
        self._bus  = None
        self._subs = dict()

    @property
    def bus(self):
        if self._bus is None:
            self._map.freeze()
            self._bus = Interface(addr_width=self._map.addr_width,
                                  data_width=self._map.data_width,
                                  name="csr")
            self._bus.memory_map = self._map
        return self._bus

    def align_to(self, alignment):
        """Align the implicit address of the next window.

        See :meth:`MemoryMap.align_to` for details.
        """
        return self._map.align_to(alignment)

    def add(self, sub_bus, *, addr=None, extend=False):
        """Add a window to a subordinate bus.

        See :meth:`MemoryMap.add_resource` for details.
        """
        if not isinstance(sub_bus, Interface):
            raise TypeError("Subordinate bus must be an instance of csr.Interface, not {!r}"
                            .format(sub_bus))
        if sub_bus.data_width != self._map.data_width:
            raise ValueError("Subordinate bus has data width {}, which is not the same as "
                             "decoder data width {}"
                             .format(sub_bus.data_width, self._map.data_width))
        self._subs[sub_bus.memory_map] = sub_bus
        return self._map.add_window(sub_bus.memory_map, addr=addr, extend=extend)

    def elaborate(self, platform):
        m = Module()

        # See Multiplexer.elaborate above.
        r_data_fanin = 0

        with m.Switch(self.bus.addr):
            for sub_map, (sub_pat, sub_ratio) in self._map.window_patterns():
                assert sub_ratio == 1

                sub_bus = self._subs[sub_map]
                m.d.comb += sub_bus.addr.eq(self.bus.addr[:sub_bus.addr_width])

                # The CSR bus interface is defined to output zero when idle, allowing us to avoid
                # adding a multiplexer here.
                r_data_fanin |= sub_bus.r_data
                m.d.comb += sub_bus.w_data.eq(self.bus.w_data)

                with m.Case(sub_pat):
                    m.d.comb += sub_bus.r_stb.eq(self.bus.r_stb)
                    m.d.comb += sub_bus.w_stb.eq(self.bus.w_stb)

        m.d.comb += self.bus.r_data.eq(r_data_fanin)

        return m
