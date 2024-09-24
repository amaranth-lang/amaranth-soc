from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from amaranth import *
from amaranth.hdl import ShapeLike
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import ceil_log2

from ..memory import MemoryMap
from .bus import Element, Signature, Multiplexer


__all__ = [
    "FieldPort", "Field", "FieldAction", "FieldActionMap", "FieldActionArray",
    "Register", "Builder", "Bridge",
]


class FieldPort(wiring.PureInterface):
    """CSR register field port.

    An interface between a :class:`Register` and one of its fields.

    Arguments
    ---------
    signature : :class:`FieldPort.Signature`
        Field port signature.
    path : iterable of :class:`str`
        Path to the field port. Optional. See :class:`amaranth.lib.wiring.PureInterface`.
    """

    class Access(enum.Enum):
        """Field access mode."""

        #: Read-only mode.
        R  = "r"
        #: Write-only mode.
        W  = "w"
        #: Read/write mode.
        RW = "rw"
        #: Not connected.
        NC = "nc"

        def readable(self):
            """Readable access mode.

            Returns
            -------
            :class:`bool`
                ``True`` if equal to :attr:`R` or :attr:`RW`.
            """
            return self == self.R or self == self.RW

        def writable(self):
            """Writable access mode.

            Returns
            -------
            :class:`bool`
                ``True`` if equal to :attr:`W` or :attr:`RW`.
            """
            return self == self.W or self == self.RW

    class Signature(wiring.Signature):
        """CSR register field port signature.

        Arguments
        ---------
        shape : :ref:`shape-like object <lang-shapelike>`
            Shape of the field.
        access : :class:`FieldPort.Access`
            Field access mode.

        Members
        -------
        r_data : :py:`In(shape)`
            Read data. Must always be valid, and is sampled when ``r_stb`` is asserted.
        r_stb : :py:`Out(1)`
            Read strobe. Fields with read side effects should perform them when this strobe is
            asserted.
        w_data : :py:`Out(shape)`
            Write data. Valid only when ``w_stb`` is asserted.
        w_stb : :py:`Out(1)`
            Write strobe. Fields should update their value or perform the write side effect when
            this strobe is asserted.
        """
        def __init__(self, shape, access):
            if not isinstance(shape, ShapeLike):
                raise TypeError(f"Field shape must be a shape-like object, not {shape!r}")
            # TODO(py3.9): Remove this. Python 3.8 and below use cls.__name__ in the error message
            # instead of cls.__qualname__.
            # FieldPort.Access(access)
            try:
                FieldPort.Access(access)
            except ValueError as e:
                raise ValueError(f"{access!r} is not a valid FieldPort.Access") from e

            self._shape  = Shape.cast(shape)
            self._access = FieldPort.Access(access)

            super().__init__({
                "r_data": In(self.shape),
                "r_stb":  Out(1),
                "w_data": Out(self.shape),
                "w_stb":  Out(1),
            })

        @property
        def shape(self):
            """Field shape.

            Returns
            -------
            :class:`amaranth.hdl.Shape`
            """
            return self._shape

        @property
        def access(self):
            """Field access mode.

            Returns
            -------
            :class:`FieldPort.Access`
            """
            return self._access

        def create(self, *, path=None, src_loc_at=0):
            """Create a compatible interface.

            See :meth:`amaranth.lib.wiring.Signature.create` for details.

            Returns
            -------
            :class:`FieldPort`
            """
            return FieldPort(self, path=path, src_loc_at=1 + src_loc_at)

        def __eq__(self, other):
            """Compare signatures.

            Two signatures are equal if they have the same shape and field access mode.
            """
            return (isinstance(other, FieldPort.Signature) and
                    Shape.cast(self.shape) == Shape.cast(other.shape) and
                    self.access == other.access)

        def __repr__(self):
            return f"csr.FieldPort.Signature({self.members!r})"

    def __init__(self, signature, *, path=None, src_loc_at=0):
        if not isinstance(signature, FieldPort.Signature):
            raise TypeError(f"This interface requires a csr.FieldPort.Signature, not "
                            f"{signature!r}")
        super().__init__(signature, path=path, src_loc_at=1 + src_loc_at)

    @property
    def shape(self):
        """Field shape.

        Returns
        -------
        :class:`amaranth.hdl.Shape`
        """
        return self.signature.shape

    @property
    def access(self):
        """Field access mode.

        Returns
        -------
        :class:`FieldPort.Access`
        """
        return self.signature.access

    def __repr__(self):
        return f"csr.FieldPort({self.signature!r})"


class Field:
    """Description of a CSR register field.

    Arguments
    ---------
    action_cls : subclass of :class:`FieldAction`
        The type of field action to be instantiated by :meth:`Field.create`.
    *args : :class:`tuple`
        Positional arguments passed to ``action_cls.__init__``.
    **kwargs : :class:`dict`
        Keyword arguments passed to ``action_cls.__init__``.
    """
    def __init__(self, action_cls, *args, **kwargs):
        if not issubclass(action_cls, FieldAction):
            raise TypeError(f"{action_cls.__qualname__} must be a subclass of csr.FieldAction")
        self._action_cls = action_cls
        self._args       = args
        self._kwargs     = kwargs

    def create(self):
        """Instantiate a field action.

        Returns
        -------
        :class:`FieldAction`
            The object returned by ``action_cls(*args, **kwargs)``.
        """
        return self._action_cls(*self._args, **self._kwargs)


class FieldAction(wiring.Component):
    """CSR register field action.

    A component mediating access between a CSR bus and a range of bits within a :class:`Register`.

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.
    access : :class:`FieldPort.Access`
        Field access mode.
    members : iterable of (:class:`str`, :class:`amaranth.lib.wiring.Member`) pairs, optional
        Additional signature members.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, access))`
        Field port.
    """
    def __init__(self, shape, access, members=()):
        members = dict(members)
        if "port" in members:
            raise ValueError(f"'port' is a reserved name, which must not be assigned to "
                             f"member {members['port']!r}")
        super().__init__({
            "port": In(FieldPort.Signature(shape, access)),
            **members,
        })


class FieldActionMap(Mapping):
    """A mapping of field actions.

    Arguments
    ---------
    fields : :class:`dict` of :class:`str` to (:class:`Field` or :class:`dict` or :class:`list`)
        Register fields. Fields are instantiated according to their type:

          - a :class:`Field` is instantiated as a :class:`FieldAction`;
          - a :class:`dict` is instantiated as a :class:`FieldActionMap`;
          - a :class:`list` is instantiated as a :class:`FieldActionArray`.
    """
    def __init__(self, fields):
        self._fields = {}

        if not isinstance(fields, dict) or len(fields) == 0:
            raise TypeError(f"Fields must be provided as a non-empty dict, not {fields!r}")

        for key, value in fields.items():
            if not isinstance(key, str) or not key:
                raise TypeError(f"Field name must be a non-empty string, not {key!r}")

            if isinstance(value, Field):
                field = value.create()
            elif isinstance(value, dict):
                field = FieldActionMap(value)
            elif isinstance(value, list):
                field = FieldActionArray(value)
            else:
                raise TypeError(f"{value!r} must either be a Field object, a dict or a list of "
                                f"Field objects")

            self._fields[key] = field

    def __getitem__(self, key):
        """Access a field by name or index.

        Returns
        --------
        :class:`FieldAction` or :class:`FieldActionMap` or :class:`FieldActionArray`
            The field instance associated with ``key``.

        Raises
        ------
        :exc:`KeyError`
            If there is no field instance associated with ``key``.
        """
        return self._fields[key]

    def __getattr__(self, name):
        """Access a field by name.

        Returns
        -------
        :class:`FieldAction` or :class:`FieldActionMap` or :class:`FieldActionArray`
            The field instance associated with ``name``.

        Raises
        ------
        :exc:`AttributeError`
            If the field map does not have a field instance associated with ``name``.
        :exc:`AttributeError`
            If ``name`` is reserved (i.e. starts with an underscore).
        """
        try:
            item = self[name]
        except KeyError:
            raise AttributeError(f"Field map does not have a field {name!r}; did you mean one of: "
                                 f"{', '.join(f'{name!r}' for name in self.keys())}?")
        if name.startswith("_"):
            raise AttributeError(f"Field map field {name!r} has a reserved name and may only be "
                                 f"accessed by indexing")
        return item

    def __iter__(self):
        """Iterate over the field map.

        Yields
        ------
        :class:`str`
            Key (name) for accessing the field.
        """
        yield from self._fields

    def __len__(self):
        """Field map size.

        Returns
        -------
        :class:`int`
            The number of items in the map.
        """
        return len(self._fields)

    def flatten(self):
        """Recursively iterate over the field map.

        Yields
        ------
        iterable of :class:`str`
            Path of the field. It is prefixed by the name of every nested :class:`FieldActionMap`
            or :class:`FieldActionArray`.
        :class:`FieldAction`
            Field instance.
        """
        for key, field in self.items():
            if isinstance(field, (FieldActionMap, FieldActionArray)):
                for sub_path, sub_field in field.flatten():
                    yield (key, *sub_path), sub_field
            else:
                yield (key,), field


class FieldActionArray(Sequence):
    """An array of CSR register fields.

    Arguments
    ---------
    fields : :class:`list` of (:class:`Field` or :class:`dict` or :class:`list`)
        Register fields. Fields are instantiated according to their type:

          - a :class:`Field` is instantiated as a :class:`FieldAction`;
          - a :class:`dict` is instantiated as a :class:`FieldActionMap`;
          - a :class:`list` is instantiated as a :class:`FieldActionArray`.
    """
    def __init__(self, fields):
        self._fields = []

        if not isinstance(fields, list) or len(fields) == 0:
            raise TypeError(f"Fields must be provided as a non-empty list, not {fields!r}")

        for item in fields:
            if isinstance(item, Field):
                field = item.create()
            elif isinstance(item, dict):
                field = FieldActionMap(item)
            elif isinstance(item, list):
                field = FieldActionArray(item)
            else:
                raise TypeError(f"{item!r} must be a Field object or a collection of Field "
                                f"objects")

            self._fields.append(field)

    def __getitem__(self, key):
        """Access a field by index.

        Returns
        -------
        :class:`FieldAction` or :class:`FieldActionMap` or :class:`FieldActionArray`
            The field instance associated with ``key``.
        """
        return self._fields[key]

    def __len__(self):
        """Field array size.

        Returns
        -------
        :class:`int`
            The number of items in the array.
        """
        return len(self._fields)

    def flatten(self):
        """Recursively iterate over the field array.

        Yields
        ------
        iterable of :class:`str`
            Path of the field. It is prefixed by the name of every nested :class:`FieldActionMap`
            or :class:`FieldActionArray`.
        :class:`FieldAction`
            Field instance.
        """
        for key, field in enumerate(self._fields):
            if isinstance(field, (FieldActionMap, FieldActionArray)):
                for sub_path, sub_field in field.flatten():
                    yield (key, *sub_path), sub_field
            else:
                yield (key,), field


class Register(wiring.Component):
    """A CSR register.

    Arguments
    ---------
    fields : :class:`dict` or :class:`list` or :class:`Field`, optional
        Collection of register fields. If omitted, a dict is populated from Python :term:`variable
        annotations <python:variable annotation>`. ``fields`` is used to create
        a :class:`FieldActionMap`, :class:`FieldActionArray`, or :class:`FieldAction`,
        depending on its type (:class:`dict`, :class:`list`, or :class:`Field`).
    access : :class:`~.csr.bus.Element.Access`
        Element access mode.

    Members
    -------
    element : :py:`In(csr.Element.Signature(shape, access))`
        Interface between this :class:`Register` and a CSR bus primitive.

    Raises
    ------
    :exc:`ValueError`
        If ``fields`` is not ``None`` and at least one :term:`variable annotation <python:variable
        annotation>` is a :class:`Field`.
    :exc:`ValueError`
        If ``element.access`` is not readable and at least one field is readable.
    :exc:`ValueError`
        If ``element.access`` is not writable and at least one field is writable.
    """

    def __init_subclass__(cls, *, access=None, **kwargs):
        if access is not None:
            # TODO(py3.9): Remove this. Python 3.8 and below use cls.__name__ in the error message
            # instead of cls.__qualname__.
            # cls._access = Element.Access(access)
            try:
                cls._access = Element.Access(access)
            except ValueError as e:
                raise ValueError(f"{access!r} is not a valid Element.Access") from e
        super().__init_subclass__(**kwargs)

    def __init__(self, fields=None, access=None):
        if hasattr(self, "__annotations__"):
            def filter_fields(src):
                if isinstance(src, Field):
                    return src
                if isinstance(src, (dict, list)):
                    items = enumerate(src) if isinstance(src, list) else src.items()
                    dst   = dict()
                    for key, value in items:
                        if new_value := filter_fields(value):
                            dst[key] = new_value
                    return list(dst.values()) if isinstance(src, list) else dst

            annot_fields = filter_fields(self.__annotations__)

            if fields is None:
                fields = annot_fields
            elif annot_fields:
                raise ValueError(f"Field collection {fields} cannot be provided in addition to "
                                 f"field annotations: {', '.join(annot_fields)}")

        if access is not None:
            # TODO(py3.9): Remove this (see above).
            try:
                access = Element.Access(access)
            except ValueError as e:
                raise ValueError(f"{access!r} is not a valid Element.Access") from e
            if hasattr(self, "_access") and access != self._access:
                raise ValueError(f"Element access mode {access} conflicts with the value "
                                 f"provided during class creation: {self._access}")
        elif hasattr(self, "_access"):
            access = self._access
        else:
            raise ValueError("Element access mode must be provided during class creation or "
                             "instantiation")

        if isinstance(fields, dict):
            self._field = FieldActionMap(fields)
        elif isinstance(fields, list):
            self._field = FieldActionArray(fields)
        elif isinstance(fields, Field):
            self._field = fields.create()
        else:
            raise TypeError(f"Field collection must be a dict, list, or Field, not {fields!r}")

        width = 0
        for field_path, field in self:
            width += Shape.cast(field.port.shape).width
            if field.port.access.readable() and not access.readable():
                raise ValueError(f"Field {'__'.join(field_path)} is readable, but element access "
                                 f"mode is {access}")
            if field.port.access.writable() and not access.writable():
                raise ValueError(f"Field {'__'.join(field_path)} is writable, but element access "
                                 f"mode is {access}")

        super().__init__({"element": In(Element.Signature(width, access))})

    @property
    def field(self):
        """Collection of field instances.

        Returns
        -------
        :class:`FieldActionMap` or :class:`FieldActionArray` or :class:`FieldAction`
        """
        return self._field

    @property
    def f(self):
        """Shorthand for :attr:`Register.field`.

        Returns
        -------
        :class:`FieldActionMap` or :class:`FieldActionArray` or :class:`FieldAction`
        """
        return self._field

    def __iter__(self):
        """Recursively iterate over the field collection.

        Yields
        ------
        iterable of :class:`str`
            Path of the field. It is prefixed by the name of every nested :class:`FieldActionMap`
            or :class:`FieldActionArray`.
        :class:`FieldAction`
            Field instance.
        """
        if isinstance(self.field, FieldAction):
            yield (), self.field
        else:
            yield from self.field.flatten()

    def elaborate(self, platform):
        m = Module()

        field_start = 0

        for field_path, field in self:
            field_width = Shape.cast(field.port.shape).width
            field_slice = slice(field_start, field_start + field_width)

            if field_path:
                m.submodules["__".join(str(key) for key in field_path)] = field
            else: # avoid empty name for a single un-named field
                m.submodules += field

            if field.port.access.readable():
                m.d.comb += [
                    self.element.r_data[field_slice].eq(field.port.r_data),
                    field.port.r_stb.eq(self.element.r_stb),
                ]
            if field.port.access.writable():
                m.d.comb += [
                    field.port.w_data.eq(self.element.w_data[field_slice]),
                    field.port.w_stb .eq(self.element.w_stb),
                ]

            field_start = field_slice.stop

        return m


class Builder:
    """CSR builder.

    A CSR builder collects a group of :class:`Register`\\ s within an address range with the goal
    of producing a :class:`~.memory.MemoryMap` of the resulting layout.

    Arguments
    ---------
    addr_width : :class:`int`
        Address width.
    data_width : :class:`int`
        Data width.
    granularity : :class:`int`, optional
        Granularity. Defaults to 8 bits.

    Raises
    ------
    :exc:`ValueError`
        If ``data_width`` is not a multiple of ``granularity``.
    """
    def __init__(self, *, addr_width, data_width, granularity=8):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise TypeError(f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width <= 0:
            raise TypeError(f"Data width must be a positive integer, not {data_width!r}")
        if not isinstance(granularity, int) or granularity <= 0:
            raise TypeError(f"Granularity must be a positive integer, not {granularity!r}")

        if data_width != (data_width // granularity) * granularity:
            raise ValueError(f"Granularity {granularity} is not a divisor of data width "
                             f"{data_width}")

        self._addr_width  = addr_width
        self._data_width  = data_width
        self._granularity = granularity

        self._registers   = dict()
        self._scope_stack = []
        self._frozen      = False

    @property
    def addr_width(self):
        """Address width.

        Returns
        -------
        :class:`int`
        """
        return self._addr_width

    @property
    def data_width(self):
        """Data width.

        Returns
        -------
        :class:`int`
        """
        return self._data_width

    @property
    def granularity(self):
        """Granularity.

        Returns
        -------
        :class:`int`
        """
        return self._granularity

    def freeze(self):
        """Freeze the builder.

        Once the builder is frozen, :class:`Register`\\ s cannot be added anymore.
        """
        self._frozen = True

    def add(self, name, reg, *, offset=None):
        """Add a register.

        Arguments
        ---------
        name : :class:`str`
            Register name.
        reg : :class:`Register`
            Register.
        offset : :class:`int`
            Register offset. Optional.

        Returns
        -------
        :class:`Register`
            ``reg``, which is added to the builder. Its name is ``name``, prefixed by the names and
            indices of any parent :meth:`~Builder.Cluster` and :meth:`~Builder.Index`.

        Raises
        ------
        :exc:`ValueError`
            If the builder is frozen.
        :exc:`ValueError`
            If ``reg`` is already added to the builder.
        :exc:`ValueError`
            If ``offset`` is not a multiple of ``self.data_width // self.granularity``.
        """
        if not isinstance(reg, Register):
            raise TypeError(f"Register must be an instance of csr.Register, not {reg!r}")
        if self._frozen:
            raise ValueError(f"Builder is frozen. Cannot add register {reg!r}")

        if name is None or not (isinstance(name, str) and name):
            raise TypeError(f"Register name must be a non-empty string, not {name!r}")

        if offset is not None:
            if not (isinstance(offset, int) and offset >= 0):
                raise TypeError(f"Offset must be a non-negative integer, not {offset!r}")
            ratio = self.data_width // self.granularity
            if offset % ratio != 0:
                raise ValueError(f"Offset {offset:#x} must be a multiple of {ratio:#x} bytes")

        if id(reg) in self._registers:
            _, other_name, other_offset = self._registers[id(reg)]
            error_msg = f"Register {reg!r} is already added with name {other_name}"
            if other_offset is None:
                error_msg += " at an implicit offset"
            else:
                error_msg += f" at an explicit offset {other_offset:#x}"
            raise ValueError(error_msg)

        self._registers[id(reg)] = reg, (*self._scope_stack, name), offset
        return reg

    @contextmanager
    def Cluster(self, name):
        """Define a cluster.

        Arguments
        ---------
        name : :class:`str`
            Cluster name.
        """
        if not (isinstance(name, str) and name):
            raise TypeError(f"Cluster name must be a non-empty string, not {name!r}")
        self._scope_stack.append(name)
        try:
            yield
        finally:
            assert self._scope_stack.pop() == name

    @contextmanager
    def Index(self, index):
        """Define an array index.

        Arguments
        ---------
        index : :class:`int`
            Array index.
        """
        if not (isinstance(index, int) and index >= 0):
            raise TypeError(f"Array index must be a non-negative integer, not {index!r}")
        self._scope_stack.append(index)
        try:
            yield
        finally:
            assert self._scope_stack.pop() == index

    def as_memory_map(self):
        """Build a memory map.

        If a register was added without an explicit ``offset``, the :ref:`implicit next address
        <memory-implicit-next-address>` of the memory map is used. Otherwise, the register address
        is ``offset * granularity // data_width``.

        Registers are added to the memory map in the same order as they were added to the builder.

        Returns
        -------
        :class:`~.memory.MemoryMap`.
        """
        self.freeze()
        memory_map = MemoryMap(addr_width=self.addr_width, data_width=self.data_width)
        for reg, reg_name, reg_offset in self._registers.values():
            if reg_offset is not None:
                reg_addr = (reg_offset * self.granularity) // self.data_width
            else:
                reg_addr = None
            reg_size = (reg.element.width + self.data_width - 1) // self.data_width
            memory_map.add_resource(reg, name=reg_name, addr=reg_addr, size=reg_size,
                                    alignment=ceil_log2(reg_size))
        memory_map.freeze()
        return memory_map


class Bridge(wiring.Component):
    """CSR bridge.

    Arguments
    ---------
    memory_map : :class:`~.memory.MemoryMap`
        Memory map of :class:`Register`\\ s.

    Members
    -------
    bus : :py:`In(csr.Signature(memory_map.addr_width, memory_map.data_width))`
        CSR bus providing access to the contents of ``memory_map``.

    Raises
    ------
    :exc:`ValueError`
        If ``memory_map`` has windows.
    """
    def __init__(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"CSR bridge memory map must be an instance of MemoryMap, not "
                            f"{memory_map!r}")
        if list(memory_map.windows()):
            raise ValueError("CSR bridge memory map cannot have windows")
        for reg, reg_name, (reg_start, reg_end) in memory_map.resources():
            if not isinstance(reg, Register):
                raise TypeError(f"CSR register must be an instance of csr.Register, not {reg!r}")

        memory_map.freeze()
        self._mux = Multiplexer(memory_map)
        super().__init__({
            "bus": In(Signature(addr_width=memory_map.addr_width,
                                data_width=memory_map.data_width))
        })
        self.bus.memory_map = memory_map

    def elaborate(self, platform):
        m = Module()

        m.submodules.mux = self._mux
        for reg, reg_name, _ in self.bus.memory_map.resources():
            m.submodules["__".join(reg_name)] = reg

        connect(m, flipped(self.bus), self._mux.bus)

        return m
