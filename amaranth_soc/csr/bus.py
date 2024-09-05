from collections import defaultdict
from amaranth import *
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out, flipped
from amaranth.utils import ceil_log2

from ..memory import MemoryMap


__all__ = ["Element", "Signature", "Interface", "Decoder", "Multiplexer"]


class Element(wiring.PureInterface):
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

    class Signature(wiring.Signature):
        """Peripheral-side CSR signature.

        Parameters
        ----------
        width : int
            Width of the register.
        access : :class:`Access`
            Register access mode.

        Interface attributes
        --------------------
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
        def __init__(self, width, access):
            if not isinstance(width, int) or width < 0:
                raise TypeError(f"Width must be a non-negative integer, not {width!r}")

            self._width  = width
            self._access = Element.Access(access)

            members = {}
            if self.access.readable():
                members.update({
                    "r_data": In(self.width),
                    "r_stb":  Out(1)
                })
            if self.access.writable():
                members.update({
                    "w_data": Out(self.width),
                    "w_stb":  Out(1)
                })
            super().__init__(members)

        @property
        def width(self):
            return self._width

        @property
        def access(self):
            return self._access

        def create(self, *, path=None, src_loc_at=0):
            """Create a compatible interface.

            See :meth:`wiring.Signature.create` for details.

            Returns
            -------
            An :class:`Element` object using this signature.
            """
            return Element(self.width, self.access, path=path, src_loc_at=1 + src_loc_at)

        def __eq__(self, other):
            """Compare signatures.

            Two signatures are equal if they have the same width and register access mode.
            """
            return (isinstance(other, Element.Signature) and
                    self.width == other.width and
                    self.access == other.access)

        def __repr__(self):
            return f"csr.Element.Signature({self.members!r})"

    """Peripheral-side CSR interface.

    A low-level interface to a single atomically readable and writable register in a peripheral.
    This interface supports any register width and semantics, provided that both reads and writes
    always succeed and complete in one cycle.

    Parameters
    ----------
    width : :class:`int`
        Width of the register.
    access : :class:`Element.Access`
        Register access mode.
    path : iter(:class:`str`)
        Path to this CSR interface. Optional. See :class:`wiring.PureInterface`.
    """
    def __init__(self, width, access, *, path=None, src_loc_at=0):
        super().__init__(Element.Signature(width=width, access=access), path=path, src_loc_at=1 + src_loc_at)

    @property
    def width(self):
        return self.signature.width

    @property
    def access(self):
        return self.signature.access

    def __repr__(self):
        return f"csr.Element({self.signature!r})"


class Signature(wiring.Signature):
    """CPU-side CSR signature.

    Parameters
    ----------
    addr_width : :class:`int`
        Address width. At most ``(2 ** addr_width) * data_width`` register bits will be available.
    data_width : :class:`int`
        Data width. Registers are accessed in ``data_width`` sized chunks.

    Interface attributes
    --------------------
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
    def __init__(self, *, addr_width, data_width):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise TypeError(f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width <= 0:
            raise TypeError(f"Data width must be a positive integer, not {data_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width

        members = {
            "addr":   Out(self.addr_width),
            "r_data": In(self.data_width),
            "r_stb":  Out(1),
            "w_data": Out(self.data_width),
            "w_stb":  Out(1),
        }
        super().__init__(members)

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    def create(self, *, path=None, src_loc_at=0):
        """Create a compatible interface.

        See :meth:`wiring.Signature.create` for details.

        Returns
        -------
        An :class:`Interface` object using this signature.
        """
        return Interface(addr_width=self.addr_width, data_width=self.data_width,
                         path=path, src_loc_at=1 + src_loc_at)

    def __eq__(self, other):
        """Compare signatures.

        Two signatures are equal if they have the same address width and data width.
        """
        return (isinstance(other, Signature) and
                self.addr_width == other.addr_width and
                self.data_width == other.data_width)

    def __repr__(self):
        return f"csr.Signature({self.members!r})"


class Interface(wiring.PureInterface):
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
    addr_width : :class:`int`
        Address width. See :class:`Signature`.
    data_width : :class:`int`
        Data width. See :class:`Signature`.
    path : iter(:class:`str`)
        Path to this CSR interface. Optional. See :class:`wiring.PureInterface`.

    Attributes
    ----------
    memory_map: :class:`MemoryMap`
        Memory map of the bus. Optional.
    """
    def __init__(self, *, addr_width, data_width, path=None, src_loc_at=0):
        super().__init__(Signature(addr_width=addr_width, data_width=data_width),
                         path=path, src_loc_at=1 + src_loc_at)
        self._memory_map = None

    @property
    def addr_width(self):
        return self.signature.addr_width

    @property
    def data_width(self):
        return self.signature.data_width

    @property
    def memory_map(self):
        if self._memory_map is None:
            raise AttributeError(f"{self!r} does not have a memory map")
        return self._memory_map

    @memory_map.setter
    def memory_map(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"Memory map must be an instance of MemoryMap, not {memory_map!r}")
        if memory_map.addr_width != self.addr_width:
            raise ValueError(f"Memory map has address width {memory_map.addr_width}, which is not "
                             f"the same as bus interface address width {self.addr_width}")
        if memory_map.data_width != self.data_width:
            raise ValueError(f"Memory map has data width {memory_map.data_width}, which is not the "
                             f"same as bus interface data width {self.data_width}")
        self._memory_map = memory_map

    def __repr__(self):
        return f"csr.Interface({self.signature!r})"


class Multiplexer(wiring.Component):
    class _Shadow:
        class Chunk:
            """The interface between a CSR multiplexer and a shadow register chunk."""
            def __init__(self, shadow, offset, registers):
                self.name = f"{shadow.name}__{offset}"
                self.data = Signal(shadow.granularity, name=f"{self.name}__data")
                self.r_en = Signal(name=f"{self.name}__r_en")
                self.w_en = Signal(name=f"{self.name}__w_en")
                self._registers = tuple(registers)

            def registers(self):
                """Iterate the address ranges of CSR registers using this chunk."""
                yield from self._registers

        """CSR multiplexer shadow register.

        Attributes
        ----------
        name : :class:`str`
            Name of the shadow register.
        granularity : :class:`int`
            Amount of bits stored in a chunk of the shadow register.
        overlaps : :class:`int`
            Maximum number of CSR registers that can share a shadow register chunk. Optional.
            If ``None``, it is implicitly set by :meth:`Multiplexer._Shadow.prepare`.
        """
        def __init__(self, granularity, overlaps, *, name):
            assert isinstance(name, str)
            assert isinstance(granularity, int) and granularity >= 0
            assert overlaps is None or isinstance(overlaps, int) and overlaps >= 0
            self.name        = name
            self.granularity = granularity
            self.overlaps    = overlaps
            self._ranges     = set()
            self._size       = 1
            self._chunks     = None

        @property
        def size(self):
            """Size of the shadow register.

            Returns
            -------
            :class:`int`
                The amount of :class:`Multiplexer._Shadow.Chunk`s of the shadow. It can increase
                by calling :meth:`Multiplexer._Shadow.add` or :meth:`Multiplexer._Shadow.prepare`.
            """
            return self._size

        def add(self, reg_range):
            """Add a CSR register to the shadow.

            Arguments
            ---------
            reg_range : :class:`range`
                Address range of a CSR register. It uses ``2 ** ceil_log2(reg_range.stop -
                reg_range.start)`` chunks of the shadow register. If this amount is greater than
                :attr:`~Multiplexer._Shadow.size`, it replaces the latter.
            """
            assert isinstance(reg_range, range)
            self._ranges.add(reg_range)
            reg_size   = 2 ** ceil_log2(reg_range.stop - reg_range.start)
            self._size = max(self._size, reg_size)

        def decode_address(self, addr, reg_range):
            """Decode a CSR bus address into a shadow register offset.

            Returns
            -------
            :class:`int`
                The shadow register offset corresponding to the :class:`Multiplexer._Shadow.Chunk`
                used by ``addr``.

                The address decoding scheme is illustrated by the following example:
                    * ``addr`` is ``0x1c``;
                    * ``reg_range`` is ``range(0x1b, 0x1f)``;
                    * the :attr:`~Multiplexer._Shadow.size` of the shadow is ``16``.

                The lower bits of the offset would be ``0b00``, extracted from ``addr``:

                .. code-block::

                    +----+--+--+
                    |0001|11|00|
                    +----+--+--+
                            │  └─ 0
                            └──── ceil_log2(reg_range.stop - reg_range.start)

                The upper bits of the offset would be ``0b10``, extracted from ``reg_range.start``:

                .. code-block::

                    +----+--+--+
                    |0001|10|11|
                    +----+--+--+
                         │  │
                         │  └──── ceil_log2(reg_range.stop - reg_range.start)
                         └─────── log2(self.size)

                The decoded offset would therefore be ``8`` (i.e. ``0b1000``).
            """
            assert reg_range in self._ranges and addr in reg_range
            reg_size  = 2 ** ceil_log2(reg_range.stop - reg_range.start)
            self_mask = self.size - 1
            reg_mask  = reg_size - 1
            return reg_range.start & self_mask & ~reg_mask | addr & reg_mask

        def encode_offset(self, offset, reg_range):
            """Encode a shadow register offset into a CSR bus address.

            Returns
            -------
            :class:`int`
                The bus address in ``reg_range`` using the :class:`Multiplexer._Shadow.Chunk`
                located at ``offset``. See :meth:`~Multiplexer._Shadow.decode_address` for details.
            """
            assert reg_range in self._ranges and isinstance(offset, int)
            reg_size = 2 ** ceil_log2(reg_range.stop - reg_range.start)
            return reg_range.start + ((offset - reg_range.start) % reg_size)

        def prepare(self):
            """Balance out and instantiate the shadow register chunks.

            The scheme used by :meth:`~Multiplexer._Shadow.decode_address` allows multiple bus
            addresses to be decoded to the same shadow register offset. Depending on the platform
            and its toolchain, this may create nets with high fan-in (if the chunk is read from
            the bus) or fan-out (if written), which may impact timing closure or resource usage.

            If any shadow register offset is aliased to more bus addresses than permitted by the
            :attr:`~Multiplexer._Shadow.overlaps` constraint, the :attr:`~Multiplexer._Shadow.size`
            of the shadow is doubled. This increases the number of address bits used for decoding,
            which effectively balances chunk usage across the shadow register.

            This method is recursive until the overlap constraint is satisfied.
            """
            if isinstance(self._ranges, frozenset):
                return
            if self.overlaps is None:
                self.overlaps = len(self._ranges)

            registers = defaultdict(list)
            balanced  = True

            # sort ranges in an arbitrary but nice fashion so that we build registers and so create
            # chunks and elaborate their connections deterministically
            ranges = sorted(self._ranges, key=lambda r: (r.start, r.stop, r.step))
            for reg_range in ranges:
                for chunk_addr in reg_range:
                    chunk_offset = self.decode_address(chunk_addr, reg_range)
                    if len(registers[chunk_offset]) > self.overlaps:
                        balanced = False
                        break
                    registers[chunk_offset].append(reg_range)

            if balanced:
                self._ranges = frozenset(self._ranges)
                self._chunks = dict()
                for chunk_offset, chunk_registers in registers.items():
                    chunk = Multiplexer._Shadow.Chunk(self, chunk_offset, chunk_registers)
                    self._chunks[chunk_offset] = chunk
            else:
                self._size *= 2
                self.prepare()

        def chunks(self):
            """Iterate shadow register chunks used by at least one CSR register."""
            for chunk_offset, chunk in self._chunks.items():
                yield chunk_offset, chunk

    """CSR register multiplexer.

    An address-based multiplexer for CSR registers implementing atomic updates.

    This implementation assumes the following from the CSR bus:
        * an initiator must have exclusive ownership over the multiplexer for the full duration of
          a register transaction;
        * an initiator must access a register in ascending order of addresses, but it may abort a
          transaction after any bus cycle.

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
          to 1 (i.e. `memory_map.alignment` should be set to 0), and each *w*-bit register would
          occupy *ceil(w/n)* addresses from the CPU perspective, requiring the same amount of
          memory instructions to access.
        * The CPU could also access the CSR bus through a width down-converter, which would issue
          *k/n* CSR accesses for each CPU access. In this case, the register alignment should be
          set to *k/n*, and each *w*-bit register would occupy *ceil(w/k)* addresses from the CPU
          perspective, requiring the same amount of memory instructions to access.

    If the register alignment (i.e. `2 ** memory_map.alignment`) is greater than 1, it affects
    which CSR bus write is considered a write to the last register chunk. For example, if a 24-bit
    register is used with a 8-bit CSR bus and a CPU with a 32-bit datapath, a write to this
    register requires 4 CSR bus writes to complete and the 4th write is the one that actually
    writes the value to the register. This allows determining write latency solely from the amount
    of addresses the register occupies in the CPU address space, and the width of the CSR bus.

    Parameters
    ----------
    memory_map : :class:`..memory.MemoryMap`
        Memory map of CSR registers.
    shadow_overlaps : int
        Maximum number of CSR registers that can share a chunk of a shadow register.
        Optional. If ``None``, any number of CSR registers can share a shadow chunk.
        See :class:`Multiplexer._Shadow` for details.

    Attributes
    ----------
    bus : :class:`Interface`
        CSR bus providing access to registers.
    """
    def __init__(self, memory_map, *, shadow_overlaps=None):
        self._check_memory_map(memory_map)
        self._r_shadow = self._Shadow(memory_map.data_width, shadow_overlaps, name="r_shadow")
        self._w_shadow = self._Shadow(memory_map.data_width, shadow_overlaps, name="w_shadow")
        super().__init__({
            "bus": In(Signature(addr_width=memory_map.addr_width,
                                data_width=memory_map.data_width))
        })
        self.bus.memory_map = memory_map

    def _check_memory_map(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"CSR multiplexer memory map must be an instance of MemoryMap, not "
                            f"{memory_map!r}")
        if list(memory_map.windows()):
            raise ValueError("CSR multiplexer memory map cannot have windows")
        for reg, reg_name, (reg_start, reg_end) in memory_map.resources():
            if not ("element" in reg.signature.members and
                    reg.signature.members["element"].flow == Out and
                    reg.signature.members["element"].is_signature and
                    isinstance(reg.signature.members["element"].signature, Element.Signature)):
                raise AttributeError(f"Signature of CSR register {reg_name} must have a "
                                     f"csr.Element.Signature member named 'element' and oriented "
                                     f"as wiring.Out")

    def elaborate(self, platform):
        m = Module()

        for reg, _, (reg_start, reg_end) in self.bus.memory_map.resources():
            reg_range = range(reg_start, reg_end)
            if reg.element.access.readable():
                self._r_shadow.add(reg_range)
            if reg.element.access.writable():
                self._w_shadow.add(reg_range)

        self._r_shadow.prepare()
        self._w_shadow.prepare()

        # Instead of a straightforward multiplexer for reads, use an address comparator for each
        # shadow register chunk, AND the comparator output with the chunk contents, and OR all of
        # those together. If the toolchain doesn't already synthesize multiplexer trees this way,
        # this trick can save a significant amount of logic, since e.g. one 4-LUT can pack one
        # 2-MUX, but two 2-AND or 2-OR gates.
        r_data_fanin = 0

        for chunk_offset, r_chunk in self._r_shadow.chunks():
            # Use the same trick to select which CSR register is read into a shadow register chunk.
            r_chunk_w_en_fanin = 0
            r_chunk_data_fanin = 0

            m.d.sync += r_chunk.r_en.eq(0)

            with m.Switch(self.bus.addr):
                for reg_range in r_chunk.registers():
                    chunk_addr = self._r_shadow.encode_offset(chunk_offset, reg_range)
                    reg        = self.bus.memory_map.decode_address(reg_range.start)
                    reg_offset = chunk_addr - reg_range.start
                    reg_r_data = reg.element.r_data.word_select(reg_offset, self.bus.data_width)

                    with m.Case(chunk_addr):
                        if chunk_addr == reg_range.start:
                            m.d.comb += reg.element.r_stb.eq(self.bus.r_stb)
                        # Delay by 1 cycle, allowing reads to be pipelined.
                        m.d.sync += r_chunk.r_en.eq(self.bus.r_stb)

                    r_chunk_w_en_fanin |= reg.element.r_stb
                    r_chunk_data_fanin |= Mux(reg.element.r_stb, reg_r_data, 0)

            m.d.comb += r_chunk.w_en.eq(r_chunk_w_en_fanin)
            with m.If(r_chunk.w_en):
                m.d.sync += r_chunk.data.eq(r_chunk_data_fanin)

            r_data_fanin |= Mux(r_chunk.r_en, r_chunk.data, 0)

        m.d.comb += self.bus.r_data.eq(r_data_fanin)

        for chunk_offset, w_chunk in self._w_shadow.chunks():
            with m.Switch(self.bus.addr):
                for reg_range in w_chunk.registers():
                    chunk_addr = self._w_shadow.encode_offset(chunk_offset, reg_range)
                    reg        = self.bus.memory_map.decode_address(reg_range.start)
                    reg_offset = chunk_addr - reg_range.start
                    reg_w_data = reg.element.w_data.word_select(reg_offset, self.bus.data_width)

                    if chunk_addr == reg_range.stop - 1:
                        m.d.sync += reg.element.w_stb.eq(0)

                    with m.Case(chunk_addr):
                        if chunk_addr == reg_range.stop - 1:
                            # Delay by 1 cycle, avoiding combinatorial paths through
                            # the CSR bus and into CSR registers.
                            m.d.sync += reg.element.w_stb.eq(self.bus.w_stb)
                        m.d.comb += w_chunk.w_en.eq(self.bus.w_stb)

                    m.d.comb += reg_w_data.eq(w_chunk.data)

            with m.If(w_chunk.w_en):
                m.d.sync += w_chunk.data.eq(self.bus.w_data)

        return m


class Decoder(wiring.Component):
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
    alignment : int, power-of-2 exponent
        Window alignment. See :class:`..memory.MemoryMap`.

    Attributes
    ----------
    bus : :class:`Interface`
        CSR bus providing access to subordinate buses.
    """
    def __init__(self, *, addr_width, data_width, alignment=0):
        super().__init__({"bus": In(Signature(addr_width=addr_width, data_width=data_width))})
        self.bus.memory_map = MemoryMap(addr_width=addr_width, data_width=data_width,
                                        alignment=alignment)
        self._subs = dict()

    def align_to(self, alignment):
        """Align the implicit address of the next window.

        See :meth:`MemoryMap.align_to` for details.
        """
        return self.bus.memory_map.align_to(alignment)

    def add(self, sub_bus, *, name=None, addr=None):
        """Add a window to a subordinate bus.

        See :meth:`MemoryMap.add_window` for details.
        """
        if isinstance(sub_bus, wiring.FlippedInterface):
            sub_bus_unflipped = flipped(sub_bus)
        else:
            sub_bus_unflipped = sub_bus
        if not isinstance(sub_bus_unflipped, Interface):
            raise TypeError(f"Subordinate bus must be an instance of csr.Interface, not "
                            f"{sub_bus_unflipped!r}")
        if sub_bus.data_width != self.bus.data_width:
            raise ValueError(f"Subordinate bus has data width {sub_bus.data_width}, which is not "
                             f"the same as decoder data width {self.bus.data_width}")
        self._subs[sub_bus.memory_map] = sub_bus
        return self.bus.memory_map.add_window(sub_bus.memory_map, name=name, addr=addr)

    def elaborate(self, platform):
        m = Module()

        # See Multiplexer.elaborate above.
        r_data_fanin = 0

        with m.Switch(self.bus.addr):
            for sub_map, sub_name, (sub_pat, sub_ratio) in self.bus.memory_map.window_patterns():
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
