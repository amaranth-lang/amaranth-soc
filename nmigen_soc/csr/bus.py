from functools import reduce
from nmigen import *
from nmigen import tracer


__all__ = ["Element", "Interface", "Decoder"]


class Element(Record):
    """Peripheral-side CSR interface.

    A low-level interface to a single atomically readable and writable register in a peripheral.
    This interface supports any register width and semantics, provided that both reads and writes
    always succeed and complete in one cycle.

    Parameters
    ----------
    width : int
        Width of the register.
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
        if access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        self.width  = width
        self.access = access

        layout = []
        if "r" in self.access:
            layout += [
                ("r_data", width),
                ("r_stb",  1),
            ]
        if "w" in self.access:
            layout += [
                ("w_data", width),
                ("w_stb",  1),
            ]
        super().__init__(layout, name=name, src_loc_at=1)


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
    addr : Signal(addr_width)
        Address for reads and writes.
    r_data : Signal(data_width)
        Read data. Valid on the next cycle after ``r_stb`` is asserted.
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

        super().__init__([
            ("addr",    addr_width),
            ("r_data",  data_width),
            ("r_stb",   1),
            ("w_data",  data_width),
            ("w_stb",   1),
        ], name=name, src_loc_at=1)


class Decoder(Elaboratable):
    """CSR bus decoder.

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
        Register alignment. The address assigned to each register will be a multiple of
        ``2 ** alignment``.

    Attributes
    ----------
    bus : :class:`Interface`
        CSR bus providing access to registers.
    """
    def __init__(self, *, addr_width, data_width, alignment=0):
        self.bus = Interface(addr_width=addr_width, data_width=data_width)

        if not isinstance(alignment, int) or alignment < 0:
            raise ValueError("Alignment must be a non-negative integer, not {!r}"
                             .format(alignment))
        self.alignment = alignment

        self._next_addr = 0
        self._elements  = dict()

    def add(self, element):
        """Add a register.

        Arguments
        ---------
        element : :class:`Element`
            Interface of the register.

        Return value
        ------------
        An ``(addr, size)`` tuple, where ``addr`` is the address assigned to the first chunk of
        the register, and ``size`` is the amount of chunks it takes, which may be greater than
        ``element.size // self.data_width`` due to alignment.
        """
        if not isinstance(element, Element):
            raise TypeError("Element must be an instance of csr.Element, not {!r}"
                            .format(element))

        addr = self.align_to(self.alignment)
        self._next_addr += (element.width + self.bus.data_width - 1) // self.bus.data_width
        size = self.align_to(self.alignment) - addr
        self._elements[addr] = element, size
        return addr, size

    def align_to(self, alignment):
        """Align the next register explicitly.

        Arguments
        ---------
        alignment : int
            Register alignment. The address assigned to the next register will be a multiple of
            ``2 ** alignment`` or ``2 ** self.alignment``, whichever is greater.

        Return value
        ------------
        Address of the next register.
        """
        if not isinstance(alignment, int) or alignment < 0:
            raise ValueError("Alignment must be a non-negative integer, not {!r}"
                             .format(alignment))

        align_chunks = 1 << alignment
        if self._next_addr % align_chunks != 0:
            self._next_addr += align_chunks - (self._next_addr % align_chunks)
        return self._next_addr

    def elaborate(self, platform):
        m = Module()

        # Instead of a straightforward multiplexer for reads, use a per-element address comparator,
        # AND the shadow register chunk with the comparator output, and OR all of those together.
        # If the toolchain doesn't already synthesize multiplexer trees this way, this trick can
        # save a significant amount of logic, since e.g. one 4-LUT can pack one 2-MUX, but two
        # 2-AND or 2-OR gates.
        r_data_fanin = 0

        for elem_addr, (elem, elem_size) in self._elements.items():
            shadow = Signal(elem.width, name="{}__shadow".format(elem.name))
            if "w" in elem.access:
                m.d.comb += elem.w_data.eq(shadow)

            # Enumerate every address used by the register explicitly, rather than using
            # arithmetic comparisons, since some toolchains (e.g. Yosys) are too eager to infer
            # carry chains for comparisons, even with a constant. (Register sizes don't have
            # to be powers of 2.)
            with m.Switch(self.bus.addr):
                for chunk_offset in range(elem_size):
                    chunk_slice = slice(chunk_offset * self.bus.data_width,
                                        (chunk_offset + 1) * self.bus.data_width)
                    with m.Case(elem_addr + chunk_offset):
                        if "r" in elem.access:
                            chunk_r_stb = Signal(self.bus.data_width,
                                name="{}__r_stb_{}".format(elem.name, chunk_offset))
                            r_data_fanin |= Mux(chunk_r_stb, shadow[chunk_slice], 0)
                            if chunk_offset == 0:
                                m.d.comb += elem.r_stb.eq(self.bus.r_stb)
                                with m.If(self.bus.r_stb):
                                    m.d.sync += shadow.eq(elem.r_data)
                            # Delay by 1 cycle, allowing reads to be pipelined.
                            m.d.sync += chunk_r_stb.eq(self.bus.r_stb)

                        if "w" in elem.access:
                            if chunk_offset == elem_size - 1:
                                # Delay by 1 cycle, avoiding combinatorial paths through
                                # the CSR bus and into CSR registers.
                                m.d.sync += elem.w_stb.eq(self.bus.w_stb)
                            with m.If(self.bus.w_stb):
                                m.d.sync += shadow[chunk_slice].eq(self.bus.w_data)

                with m.Default():
                    m.d.sync += shadow.eq(0)

        m.d.comb += self.bus.r_data.eq(r_data_fanin)

        return m
