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
    class Access(enum.Enum):
        """Field access mode."""
        R  = "r"
        W  = "w"
        RW = "rw"
        NC = "nc"

        def readable(self):
            return self == self.R or self == self.RW

        def writable(self):
            return self == self.W or self == self.RW

    class Signature(wiring.Signature):
        """CSR register field port signature.

        Parameters
        ----------
        shape : :ref:`shape-like object <lang-shapelike>`
            Shape of the field.
        access : :class:`FieldPort.Access`
            Field access mode.

        Interface attributes
        --------------------
        r_data : Signal(shape)
            Read data. Must always be valid, and is sampled when ``r_stb`` is asserted.
        r_stb : Signal()
            Read strobe. Fields with read side effects should perform them when this strobe is
            asserted.
        w_data : Signal(shape)
            Write data. Valid only when ``w_stb`` is asserted.
        w_stb : Signal()
            Write strobe. Fields should update their value or perform the write side effect when
            this strobe is asserted.
        """
        def __init__(self, shape, access):
            if not isinstance(shape, ShapeLike):
                raise TypeError(f"Field shape must be a shape-like object, not {shape!r}")

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
            return self._shape

        @property
        def access(self):
            return self._access

        def create(self, *, path=None, src_loc_at=0):
            """Create a compatible interface.

            See :meth:`wiring.Signature.create` for details.

            Returns
            -------
            A :class:`FieldPort` object using this signature.
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

    """CSR register field port.

    An interface between a CSR register and one of its fields.

    Parameters
    ----------
    signature : :class:`FieldPort.Signature`
        Field port signature.
    path : iter(:class:`str`)
        Path to the field port. Optional. See :class:`wiring.PureInterface`.

    Attributes
    ----------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field. See :class:`FieldPort.Signature`.
    access : :class:`FieldPort.Access`
        Field access mode. See :class:`FieldPort.Signature`.

    Raises
    ------
    :exc:`TypeError`
        If ``signature`` is not a :class:`FieldPort.Signature`.
    """
    def __init__(self, signature, *, path=None, src_loc_at=0):
        if not isinstance(signature, FieldPort.Signature):
            raise TypeError(f"This interface requires a csr.FieldPort.Signature, not "
                            f"{signature!r}")
        super().__init__(signature, path=path, src_loc_at=1 + src_loc_at)

    @property
    def shape(self):
        return self.signature.shape

    @property
    def access(self):
        return self.signature.access

    def __repr__(self):
        return f"csr.FieldPort({self.signature!r})"


class Field:
    """Description of a CSR register field.

    Parameters
    ----------
    action_cls : :class:`FieldAction` subclass
        The type of field action to be instantiated by :meth:`Field.create`.
    *args : :class:`tuple`
        Positional arguments passed to ``action_cls.__init__``.
    **kwargs : :class:`dict`
        Keyword arguments passed to ``action_cls.__init__``.

    Raises
    ------
    :exc:`TypeError`
        If ``action_cls`` is not a subclass of :class:`FieldAction`.
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

    A :class:`~wiring.Component` mediating access between a CSR bus and a range of bits within a
    :class:`Register`.

    Parameters
    ----------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field. See :class:`FieldPort.Signature`.
    access : :class:`FieldPort.Access`
        Field access mode. See :class:`FieldPort.Signature`.
    members : iterable of (:class:`str`, :class:`wiring.Member`) key/value pairs
        Signature members. Optional, defaults to ``()``. A :class:`FieldPort.Signature` member
        named 'port' and oriented as input is always present in addition to these members.

    Interface attributes
    --------------------
    port : :class:`FieldPort`
        Field port.

    Raises
    ------
    :exc:`ValueError`
        If the key 'port' is used in ``members``.
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

    Parameters
    ----------
    fields : :class:`dict` of :class:`str` to (:class:`Field` or :class:`dict` or :class:`list`)
        Register fields. Fields are instantiated according to their type:
          - a :class:`Field` is instantiated as a :class:`FieldAction` (see :meth:`Field.create`);
          - a :class:`dict` is instantiated as a :class:`FieldActionMap`;
          - a :class:`list` is instantiated as a :class:`FieldArrayMap`.

    Raises
    ------
    :exc:`TypeError`
        If ``fields`` is not a dict, or is empty.
    :exc:`TypeError`
        If ``fields`` has a key that is not a string, or is empty.
    :exc:`TypeError`
        If ``fields`` has a value that is neither a :class:`Field` object, a dict or a list of
        :class:`Field` objects.
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
        iter(:class:`str`)
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

    Parameters
    ----------
    fields : :class:`list` of (:class:`Field` or :class:`dict` or :class:`list`)
        Register fields. Fields are instantiated according to their type:
          - a :class:`Field` is instantiated as a :class:`FieldAction` (see :meth:`Field.create`);
          - a :class:`dict` is instantiated as a :class:`FieldActionMap`;
          - a :class:`list` is instantiated as a :class:`FieldArrayMap`.

    Raises
    ------
    :exc:`TypeError`
        If ``fields`` is not a list, or is empty.
    :exc:`TypeError`
        If ``fields`` has an item that is neither a :class:`Field` object, a dict or a list of
        :class:`Field` objects.
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
        """Iterate recursively over the field array.

        Yields
        ------
        iter(:class:`str`)
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
    _doc_template = """
    A CSR register.

    Parameters
    ----------
    fields : :class:`dict` or :class:`list` or :class:`Field`
        Collection of register fields. If ``None`` (default), a dict is populated from Python
        :term:`variable annotations <python:variable annotations>`. ``fields`` is used to create
        a :class:`FieldActionMap`, :class:`FieldActionArray`, or :class:`FieldAction`,
        depending on its type (dict, list, or Field).
    {parameters}

    Interface attributes
    --------------------
    element : :class:`Element`
        Interface between this register and a CSR bus primitive.

    Attributes
    ----------
    field : :class:`FieldActionMap` or :class:`FieldActionArray` or :class:`FieldAction`
        Collection of field instances.
    f : :class:`FieldActionMap` or :class:`FieldActionArray` or :class:`FieldAction`
        Shorthand for :attr:`Register.field`.

    Raises
    ------
    :exc:`TypeError`
        If ``fields`` is neither ``None``, a :class:`dict`, a :class:`list`, or a :class:`Field`.
    :exc:`ValueError`
        If ``fields`` is not ``None`` and at least one variable annotation is a :class:`Field`.
    :exc:`ValueError`
        If ``element.access`` is not readable and at least one field is readable.
    :exc:`ValueError`
        If ``element.access`` is not writable and at least one field is writable.
    """

    __doc__ = _doc_template.format(parameters="""
    access : :class:`Element.Access`
        Element access mode.
    """)

    def __init_subclass__(cls, *, access=None, **kwargs):
        if access is not None:
            cls._access = Element.Access(access)
            cls.__doc__ = cls._doc_template.format(parameters="")
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
            access = Element.Access(access)
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

        super().__init__({"element": Out(Element.Signature(width, access))})

    @property
    def field(self):
        return self._field

    @property
    def f(self):
        return self._field

    def __iter__(self):
        """Recursively iterate over the field collection.

        Yields
        ------
        iter(:class:`str`)
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

    A CSR builder can organize a group of registers within an address range and convert it to a
    :class:`MemoryMap` for consumption by other SoC primitives.

    Parameters
    ----------
    addr_width : :class:`int`
        Address width.
    data_width : :class:`int`
        Data width.
    granularity : :class:`int`
        Granularity. Optional, defaults to 8 bits.

    Raises
    ------
    :exc:`TypeError`
        If ``addr_width`` is not a positive integer.
    :exc:`TypeError`
        If ``data_width`` is not a positive integer.
    :exc:`TypeError`
        If ``granularity`` is not a positive integer.
    :exc:`ValueError`
        If ``granularity`` is not a divisor of ``data_width``
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
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def granularity(self):
        return self._granularity

    def freeze(self):
        """Freeze the builder.

        Once the builder is frozen, CSR registers cannot be added anymore.
        """
        self._frozen = True

    def add(self, name, reg, *, offset=None):
        """Add a CSR register.

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
        :exc:`TypeError`
            If ``name`` is not a string, or is empty.
        :exc:`TypeError`
            If ``reg` is not an instance of :class:`Register`.
        :exc:`ValueError`
            If ``reg`` is already added to the builder.
        :exc:`TypeError`
            If ``offset`` is not an integer, or is negative.
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

        Raises
        ------
        :exc:`TypeError`
            If ``name`` is not a string, or is empty.
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

        Raises
        ------
        :exc:`TypeError`
            If ``index`` is not an integer, or is negative.
        """
        if not (isinstance(index, int) and index >= 0):
            raise TypeError(f"Array index must be a non-negative integer, not {index!r}")
        self._scope_stack.append(index)
        try:
            yield
        finally:
            assert self._scope_stack.pop() == index

    def as_memory_map(self):
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

    Parameters
    ----------
    memory_map : :class:`MemoryMap`
        Memory map of CSR registers.

    Interface attributes
    --------------------
    bus : :class:`Interface`
        CSR bus providing access to the contents of ``memory_map``.

    Raises
    ------
    :exc:`TypeError`
        If ``memory_map`` is not a :class:`MemoryMap` object.
    :exc:`ValueError`
        If ``memory_map`` has windows.
    :exc:`TypeError`
        If ``memory_map`` has resources that are not :class:`Register` objects.
    """
    def __init__(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"CSR bridge memory map must be an instance of MemoryMap, not {memory_map!r}")
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
