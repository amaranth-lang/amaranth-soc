import bisect

from nmigen.utils import bits_for


__all__ = ["MemoryMap"]


class _RangeMap:
    """Range map.

    A range map is a mapping from non-overlapping ranges to arbitrary values.
    """
    def __init__(self):
        self._keys   = []
        self._values = dict()
        self._starts = []
        self._stops  = []

    def insert(self, key, value):
        assert isinstance(key, range)
        assert not self.overlaps(key)

        start_idx = bisect.bisect_right(self._starts, key.start)
        stop_idx  = bisect.bisect_left(self._stops, key.stop)
        assert start_idx == stop_idx

        self._starts.insert(start_idx, key.start)
        self._stops.insert(stop_idx, key.stop)
        self._keys.insert(start_idx, key)
        self._values[key] = value

    def get(self, point):
        point_idx = bisect.bisect_right(self._stops, point)
        if point_idx < len(self._keys):
            point_range = self._keys[point_idx]
            if point >= point_range.start and point < point_range.stop:
                return self._values[point_range]

    def overlaps(self, key):
        start_idx = bisect.bisect_right(self._stops, key.start)
        stop_idx  = bisect.bisect_left(self._starts, key.stop)
        return [self._values[key] for key in self._keys[start_idx:stop_idx]]

    def items(self):
        for key in self._keys:
            yield key, self._values[key]


class MemoryMap:
    """Memory map.

    A memory map is a hierarchical description of an address space, describing the structure of
    address decoders of peripherals as well as bus bridges. It is built by adding resources
    (range allocations for registers, memory, etc) and windows (range allocations for bus bridges),
    and can be queried later to determine the address of any given resource from a specific
    vantage point in the design.

    Address assignment
    ------------------

    To simplify address assignment, each memory map has an implicit next address, starting at 0.
    If a resource or a window is added without specifying an address explicitly, the implicit next
    address is used. In any case, the implicit next address is set to the address immediately
    following the newly added resource or window.

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int
        Data width.
    alignment : int
        Range alignment. Each added resource and window will be placed at an address that is
        a multiple of ``2 ** alignment``, and its size will be rounded up to be a multiple of
        ``2 ** alignment``.
    """
    def __init__(self, *, addr_width, data_width, alignment=0):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise ValueError("Address width must be a positive integer, not {!r}"
                             .format(addr_width))
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError("Data width must be a positive integer, not {!r}"
                             .format(data_width))
        if not isinstance(alignment, int) or alignment < 0:
            raise ValueError("Alignment must be a non-negative integer, not {!r}"
                             .format(alignment))

        self._addr_width = addr_width
        self._data_width = data_width
        self._alignment  = alignment

        self._ranges     = _RangeMap()
        self._resources  = dict()
        self._windows    = dict()

        self._next_addr  = 0
        self._frozen     = False

    @property
    def addr_width(self):
        return self._addr_width

    @addr_width.setter
    def addr_width(self, addr_width):
        if self._frozen:
            raise ValueError("Memory map has been frozen. Address width cannot be extended "
                             "further")
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise ValueError("Address width must be a positive integer, not {!r}"
                             .format(addr_width))
        if addr_width < self._addr_width:
            raise ValueError("Address width {!r} must not be less than its previous value {!r}, "
                             "because resources that were previously added may not fit anymore"
                             .format(addr_width, self._addr_width))
        self._addr_width = addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def alignment(self):
        return self._alignment

    def freeze(self):
        """Freeze the memory map.

        Once frozen, the memory map cannot be extended anymore. Resources and windows may
        still be added, as long as they fit within the address space bounds.
        """
        self._frozen = True

    @staticmethod
    def _align_up(value, alignment):
        if value % (1 << alignment) != 0:
            value += (1 << alignment) - (value % (1 << alignment))
        return value

    def align_to(self, alignment):
        """Align the implicit next address.

        Arguments
        ---------
        alignment : int
            Address alignment. The start of the implicit next address will be a multiple of
            ``2 ** max(alignment, self.alignment)``.

        Return value
        ------------
        Implicit next address.
        """
        if not isinstance(alignment, int) or alignment < 0:
            raise ValueError("Alignment must be a non-negative integer, not {!r}"
                             .format(alignment))
        self._next_addr = self._align_up(self._next_addr, max(alignment, self.alignment))
        return self._next_addr

    def _compute_addr_range(self, addr, size, step=1, *, alignment, extend):
        if addr is not None:
            if not isinstance(addr, int) or addr < 0:
                raise ValueError("Address must be a non-negative integer, not {!r}"
                                 .format(addr))
            if addr % (1 << self.alignment) != 0:
                raise ValueError("Explicitly specified address {:#x} must be a multiple of "
                                 "{:#x} bytes"
                                 .format(addr, 1 << alignment))
        else:
            addr = self._align_up(self._next_addr, alignment)

        if not isinstance(size, int) or size < 0:
            raise ValueError("Size must be a non-negative integer, not {!r}"
                             .format(size))
        size = self._align_up(max(size, 1), alignment)

        if addr > (1 << self.addr_width) or addr + size > (1 << self.addr_width):
            if extend:
                self.addr_width = bits_for(addr + size)
            else:
                raise ValueError("Address range {:#x}..{:#x} out of bounds for memory map spanning "
                                 "range {:#x}..{:#x} ({} address bits)"
                                 .format(addr, addr + size, 0, 1 << self.addr_width, self.addr_width))

        addr_range = range(addr, addr + size, step)
        overlaps = self._ranges.overlaps(addr_range)
        if overlaps:
            overlap_descrs = []
            for overlap in overlaps:
                if overlap in self._resources:
                    resource_range = self._resources[overlap]
                    overlap_descrs.append("resource {!r} at {:#x}..{:#x}"
                        .format(overlap, resource_range.start, resource_range.stop))
                if overlap in self._windows:
                    window_range = self._windows[overlap]
                    overlap_descrs.append("window {!r} at {:#x}..{:#x}"
                        .format(overlap, window_range.start, window_range.stop))
            raise ValueError("Address range {:#x}..{:#x} overlaps with {}"
                             .format(addr, addr + size, ", ".join(overlap_descrs)))

        return addr_range

    def add_resource(self, resource, *, size, addr=None, alignment=None, extend=False):
        """Add a resource.

        A resource is any device on the bus that is a destination for bus transactions, e.g.
        a register or a memory block.

        Arguments
        ---------
        resource : object
            Arbitrary object representing a resource.
        addr : int or None
            Address of the resource. If ``None``, the implicit next address will be used.
            Otherwise, the exact specified address (which must be a multiple of
            ``2 ** max(alignment, self.alignment)``) will be used.
        size : int
            Size of the resource, in minimal addressable units. Rounded up to a multiple of
            ``2 ** max(alignment, self.alignment)``.
        alignment : int or None
            Alignment of the resource. If not specified, the memory map alignment is used.
        extend: bool
            Allow memory map extension. If ``True``, the upper bound of the address space is
            raised as needed, in order to fit a resource that would otherwise be out of bounds.

        Return value
        ------------
        A tuple ``(start, end)`` describing the address range assigned to the resource.

        Exceptions
        ----------
        Raises :exn:`ValueError` if the requested address and size, after alignment, would overlap
        with any resources or windows that have already been added, or would be out of bounds.
        """
        if resource in self._resources:
            addr_range = self._resources[resource]
            raise ValueError("Resource {!r} is already added at address range {:#x}..{:#x}"
                             .format(resource, addr_range.start, addr_range.stop))

        if alignment is not None:
            if not isinstance(alignment, int) or alignment < 0:
                raise ValueError("Alignment must be a non-negative integer, not {!r}"
                                 .format(alignment))
            alignment = max(alignment, self.alignment)
        else:
            alignment = self.alignment

        addr_range = self._compute_addr_range(addr, size, alignment=alignment, extend=extend)
        self._ranges.insert(addr_range, resource)
        self._resources[resource] = addr_range
        self._next_addr = addr_range.stop
        return addr_range.start, addr_range.stop

    def resources(self):
        """Iterate local resources and their address ranges.

        Non-recursively iterate resources in ascending order of their address.

        Yield values
        ------------
        A tuple ``resource, (start, end)`` describing the address range assigned to the resource.
        """
        for resource, resource_range in self._resources.items():
            yield resource, (resource_range.start, resource_range.stop)

    def add_window(self, window, *, addr=None, sparse=None, extend=False):
        """Add a window.

        A window is a device on a bus that provides access to a different bus, i.e. a bus bridge.
        It performs address translation, such that the devices on a subordinate bus have different
        addresses; the memory map reflects this address translation when resources are looked up
        through the window.

        Sparse addressing
        -----------------

        If a narrow bus is bridged to a wide bus, the bridge can perform *sparse* or *dense*
        address translation. In the sparse case, each transaction on the wide bus results in
        one transaction on the narrow bus; high data bits on the wide bus are ignored, and any
        contiguous resource on the narrow bus becomes discontiguous on the wide bus. In the dense
        case, each transaction on the wide bus results in several transactions on the narrow bus,
        and any contiguous resource on the narrow bus stays contiguous on the wide bus.

        Arguments
        ---------
        window : :class:`MemoryMap`
            A memory map describing the layout of the window.
        addr : int or None
            Address of the window. If ``None``, the implicit next address will be used after
            aligning it to ``2 ** window.addr_width``. Otherwise, the exact specified address
            (which must be a multiple of ``2 ** window.addr_width``) will be used.
        sparse : bool or None
            Address translation type. Ignored if the datapath widths of both memory maps are
            equal; must be specified otherwise.
        extend : bool
            Allow memory map extension. If ``True``, the upper bound of the address space is
            raised as needed, in order to fit a window that would otherwise be out of bounds.

        Return value
        ------------
        A tuple ``(start, end, ratio)`` describing the address range assigned to the window.
        When bridging buses of unequal data width, ``ratio`` is the amount of contiguous addresses
        on the narrower bus that are accessed for each transaction on the wider bus. Otherwise,
        it is always 1.

        Exceptions
        ----------
        Raises :exn:`ValueError` if the requested address and size, after alignment, would overlap
        with any resources or windows that have already been added, or would be out of bounds;
        if the added memory map has wider datapath than this memory map; if dense address
        translation is used and the datapath width of this memory map is not an integer multiple
        of the datapath width of the added memory map.
        """
        if not isinstance(window, MemoryMap):
            raise TypeError("Window must be a MemoryMap, not {!r}"
                            .format(window))
        if window in self._windows:
            addr_range = self._windows[window]
            raise ValueError("Window {!r} is already added at address range {:#x}..{:#x}"
                             .format(window, addr_range.start, addr_range.stop))

        if window.data_width > self.data_width:
            raise ValueError("Window has data width {}, and cannot be added to a memory map "
                             "with data width {}"
                             .format(window.data_width, self.data_width))
        if window.data_width != self.data_width:
            if sparse is None:
                raise ValueError("Address translation mode must be explicitly specified "
                                 "when adding a window with data width {} to a memory map "
                                 "with data width {}"
                                 .format(window.data_width, self.data_width))
            if not sparse and self.data_width % window.data_width != 0:
                raise ValueError("Dense addressing cannot be used because the memory map "
                                 "data width {} is not an integer multiple of window "
                                 "data width {}"
                                 .format(self.data_width, window.data_width))

        window.freeze()

        if not sparse:
            ratio = self.data_width // window.data_width
        else:
            ratio = 1
        size = (1 << window.addr_width) // ratio
        # For resources, the alignment argument of add_resource() affects both address and size
        # of the resource; aligning only the address should be done using align_to(). For windows,
        # changing the size (beyond the edge case of the window size being smaller than alignment
        # of the bus) is unlikely to be useful, so there is no alignment argument. The address of
        # a window can still be aligned using align_to().
        alignment = max(self.alignment, window.addr_width // ratio)

        addr_range = self._compute_addr_range(addr, size, ratio, alignment=alignment,
                                              extend=extend)
        self._ranges.insert(addr_range, window)
        self._windows[window] = addr_range
        self._next_addr = addr_range.stop
        return addr_range.start, addr_range.stop, addr_range.step

    def windows(self):
        """Iterate local windows and their address ranges.

        Non-recursively iterate windows in ascending order of their address.

        Yield values
        ------------
        A tuple ``window, (start, end, ratio)`` describing the address range assigned to
        the window. When bridging buses of unequal data width, ``ratio`` is the amount of
        contiguous addresses on the narrower bus that are accessed for each transaction on
        the wider bus. Otherwise, it is always 1.
        """
        for window, window_range in self._windows.items():
            yield window, (window_range.start, window_range.stop, window_range.step)

    def window_patterns(self):
        """Iterate local windows and patterns that match their address ranges.

        Non-recursively iterate windows in ascending order of their address.

        Yield values
        ------------
        A tuple ``window, (pattern, ratio)`` describing the address range assigned to the window.
        ``pattern`` is a ``self.addr_width`` wide pattern that may be used in ``Case`` or ``match``
        to determine if an address signal is within the address range of ``window``. When bridging
        buses of unequal data width, ``ratio`` is the amount of contiguous addresses on
        the narrower bus that are accessed for each transaction on the wider bus. Otherwise,
        it is always 1.
        """
        for window, window_range in self._windows.items():
            const_bits = self.addr_width - window.addr_width
            if const_bits > 0:
                const_pat = "{:0{}b}".format(window_range.start >> window.addr_width, const_bits)
            else:
                const_pat = ""
            pattern = "{}{}".format(const_pat, "-" * window.addr_width)
            yield window, (pattern, window_range.step)

    @staticmethod
    def _translate(start, end, width, window, window_range):
        assert (end - start) % window_range.step == 0
        # Accessing a resource through a dense and then a sparse window results in very strange
        # layouts that cannot be easily represented, so reject those.
        assert window_range.step == 1 or width == window.data_width
        size   = (end - start) // window_range.step
        start += window_range.start
        width *= window_range.step
        return start, start + size, width

    def all_resources(self):
        """Iterate all resources and their address ranges.

        Recursively iterate all resources in ascending order of their address, performing address
        translation for resources that are located behind a window.

        Yield values
        ------------
        A tuple ``resource, (start, end, width)`` describing the address range assigned to
        the resource. ``width`` is the amount of data bits accessed at each address, which may be
        equal to ``self.data_width``, or less if the resource is located behind a window that
        uses sparse addressing.
        """
        for addr_range, assignment in self._ranges.items():
            if assignment in self._resources:
                yield assignment, (addr_range.start, addr_range.stop, self.data_width)
            elif assignment in self._windows:
                for sub_resource, sub_descr in assignment.all_resources():
                    yield sub_resource, self._translate(*sub_descr, assignment, addr_range)
            else:
                assert False # :nocov:

    def find_resource(self, resource):
        """Find address range corresponding to a resource.

        Recursively find the address range of a resource, performing address translation for
        resources that are located behind a window.

        Arguments
        ---------
        resource
            Resource previously added to this memory map or any windows.

        Return value
        ------------
        A tuple ``(start, end, width)`` describing the address range assigned to the resource.
        ``width`` is the amount of data bits accessed at each address, which may be equal to
        ``self.data_width``, or less if the resource is located behind a window that uses sparse
        addressing.

        Exceptions
        ----------
        Raises :exn:`KeyError` if the resource is not found.
        """
        if resource in self._resources:
            resource_range = self._resources[resource]
            return resource_range.start, resource_range.stop, self.data_width

        for window, window_range in self._windows.items():
            try:
                return self._translate(*window.find_resource(resource), window, window_range)
            except KeyError:
                pass

        raise KeyError(resource)

    def decode_address(self, address):
        """Decode an address to a resource.

        Arguments
        ---------
        address : int
            Address of interest.

        Return value
        ------------
        A resource mapped to the provided address, or ``None`` if there is no such resource.
        """
        assignment = self._ranges.get(address)
        if assignment is None:
            return

        if assignment in self._resources:
            return assignment
        elif assignment in self._windows:
            addr_range = self._windows[assignment]
            return assignment.decode_address((address - addr_range.start) // addr_range.step)
        else:
            assert False # :nocov:
