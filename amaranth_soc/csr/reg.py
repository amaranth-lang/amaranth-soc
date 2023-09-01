from collections.abc import Mapping, Sequence
import enum
from amaranth import *

from ..memory import MemoryMap
from .bus import Element, Multiplexer


__all__ = ["FieldPort", "Field", "FieldMap", "FieldArray", "Register", "RegisterMap", "Bridge"]


class FieldPort:
    class Access(enum.Enum):
        """Field access mode."""
        R  = "r"
        W  = "w"
        RW = "rw"

        def readable(self):
            return self == self.R or self == self.RW

        def writable(self):
            return self == self.W or self == self.RW

    """CSR register field port.

    An interface between a CSR register and one of its fields.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    access : :class:`FieldPort.Access`
        Field access mode.

    Attributes
    ----------
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

    Raises
    ------
    :exc:`TypeError`
        If ``shape`` is not a shape-castable object.
    :exc:`ValueError`
        If ``access`` is not a member of :class:`FieldPort.Access`.
    """
    def __init__(self, shape, access):
        try:
            shape = Shape.cast(shape)
        except TypeError as e:
            raise TypeError("Field shape must be a shape-castable object, not {!r}"
                            .format(shape)) from e
        if not isinstance(access, FieldPort.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        self._shape  = shape
        self._access = FieldPort.Access(access)

        self.r_data  = Signal(shape)
        self.r_stb   = Signal()
        self.w_data  = Signal(shape)
        self.w_stb   = Signal()

    @property
    def shape(self):
        return self._shape

    @property
    def access(self):
        return self._access

    def __repr__(self):
        return "FieldPort({}, {})".format(self.shape, self.access)


class Field(Elaboratable):
    _doc_template = """
    {description}

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    access : :class:`FieldPort.Access`
        Field access mode.
    {parameters}

    Attributes
    ----------
    port : :class:`FieldPort`
        Field port.
    {attributes}
    """

    __doc__ = _doc_template.format(
    description="""
    A generic register field.
    """.strip(),
    parameters="",
    attributes="")

    def __init__(self, shape, access):
        self.port = FieldPort(shape, access)

    @property
    def shape(self):
        return self.port.shape

    @property
    def access(self):
        return self.port.access


class FieldMap(Mapping):
    """A mapping of CSR register fields.

    Parameters
    ----------
    fields : dict of :class:`str` to one of :class:`Field` or :class:`FieldMap`.
    """
    def __init__(self, fields):
        self._fields = {}

        if not isinstance(fields, Mapping) or len(fields) == 0:
            raise TypeError("Fields must be provided as a non-empty mapping, not {!r}"
                            .format(fields))

        for key, field in fields.items():
            if not isinstance(key, str) or not key:
                raise TypeError("Field name must be a non-empty string, not {!r}"
                                .format(key))
            if not isinstance(field, (Field, FieldMap, FieldArray)):
                raise TypeError("Field must be a Field or a FieldMap or a FieldArray, not {!r}"
                                .format(field))
            self._fields[key] = field

    def __getitem__(self, key):
        """Access a field by name or index.

        Returns
        --------
        :class:`Field` or :class:`FieldMap` or :class:`FieldArray`
            The field associated with ``key``.

        Raises
        ------
        :exc:`KeyError`
            If there is no field associated with ``key``.
        """
        return self._fields[key]

    def __getattr__(self, name):
        """Access a field by name.

        Returns
        -------
        :class:`Field` or :class:`FieldMap` or :class:`FieldArray`
            The field associated with ``name``.

        Raises
        ------
        :exc:`AttributeError`
            If the field map does not have a field associated with ``name``.
        :exc:`AttributeError`
            If ``name`` is reserved (i.e. starts with an underscore).
        """
        try:
            item = self[name]
        except KeyError:
            raise AttributeError("Field map does not have a field {!r}; "
                                 "did you mean one of: {}?"
                                 .format(name, ", ".join(repr(name) for name in self.keys())))
        if name.startswith("_"):
            raise AttributeError("Field map field {!r} has a reserved name and may only be "
                                 "accessed by indexing"
                                 .format(name))
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
        return len(self._fields)

    def flatten(self):
        """Recursively iterate over the field map.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field collection.
        :class:`Field`
            Register field.
        """
        for key, field in self.items():
            if isinstance(field, Field):
                yield (key,), field
            elif isinstance(field, (FieldMap, FieldArray)):
                for sub_name, sub_field in field.flatten():
                    yield (key, *sub_name), sub_field
            else:
                assert False # :nocov:


class FieldArray(Sequence):
    """An array of CSR register fields.

    Parameters
    ----------
    fields : iter(:class:`Field` or :class:`FieldMap` or :class:`FieldArray`)
        Field array members.
    """
    def __init__(self, fields):
        fields = tuple(fields)
        for field in fields:
            if not isinstance(field, (Field, FieldMap, FieldArray)):
                raise TypeError("Field must be a Field or a FieldMap or a FieldArray, not {!r}"
                                .format(field))
        self._fields = fields

    def __getitem__(self, key):
        """Access a field by index.

        Returns
        -------
        :class:`Field` or :class:`FieldMap` or :class:`FieldArray`
            The field associated with ``key``.
        """
        return self._fields[key]

    def __len__(self):
        """Field array length.

        Returns
        -------
        :class:`int`
            The number of fields in the array.
        """
        return len(self._fields)

    def flatten(self):
        """Iterate recursively over the field array.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field collection.
        :class:`Field`
            Register field.
        """
        for key, field in enumerate(self._fields):
            if isinstance(field, Field):
                yield (key,), field
            elif isinstance(field, (FieldMap, FieldArray)):
                for sub_name, sub_field in field.flatten():
                    yield (key, *sub_name), sub_field
            else:
                assert False # :nocov:


class Register(Elaboratable):
    """CSR register.

    Parameters
    ----------
    access : :class:`Element.Access`
        Register access mode.
    fields : :class:`FieldMap` or :class:`FieldArray`
        Collection of register fields. If ``None`` (default), a :class:`FieldMap` is created
        from Python :term:`variable annotations <python:variable annotations>`.

    Attributes
    ----------
    element : :class:`Element`
        Interface between this register and a CSR bus primitive.
    fields : :class:`FieldMap` or :class:`FieldArray`
        Collection of register fields.
    f : :class:`FieldMap` or :class:`FieldArray`
        Shorthand for :attr:`Register.fields`.

    Raises
    ------
    :exc:`ValueError`
        If ``access`` is not a member of :class:`Element.Access`.
    :exc:`TypeError`
        If ``fields`` is not ``None`` or a :class:`FieldMap` or a :class:`FieldArray`.
    :exc:`ValueError`
        If ``access`` is not readable and at least one field is readable.
    :exc:`ValueError`
        If ``access`` is not writable and at least one field is writable.
    """
    def __init__(self, access, fields=None):
        if not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        access = Element.Access(access)

        if hasattr(self, "__annotations__"):
            annotation_fields = {}
            for key, value in self.__annotations__.items():
                if isinstance(value, (Field, FieldMap, FieldArray)):
                    annotation_fields[key] = value

            if fields is None:
                fields = FieldMap(annotation_fields)
            elif annotation_fields:
                raise ValueError("Field collection {} cannot be provided in addition to field annotations: {}"
                                 .format(fields, ", ".join(annotation_fields.keys())))

        if not isinstance(fields, (FieldMap, FieldArray)):
            raise TypeError("Field collection must be a FieldMap or a FieldArray, not {!r}"
                            .format(fields))

        width = 0
        for field_name, field in fields.flatten():
            width += Shape.cast(field.shape).width
            if field.access.readable() and not access.readable():
                raise ValueError("Field {} is readable, but register access mode is '{}'"
                                 .format("__".join(field_name), access))
            if field.access.writable() and not access.writable():
                raise ValueError("Field {} is writable, but register access mode is '{}'"
                                 .format("__".join(field_name), access))

        self.element = Element(width, access)
        self._fields = fields

    @property
    def fields(self):
        return self._fields

    @property
    def f(self):
        return self._fields

    def __iter__(self):
        """Recursively iterate over the field collection.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field collection.
        :class:`Field`
            Register field.
        """
        yield from self.fields.flatten()

    def elaborate(self, platform):
        m = Module()

        field_start = 0

        for field_name, field in self.fields.flatten():
            m.submodules["__".join(str(key) for key in field_name)] = field

            field_slice = slice(field_start, field_start + Shape.cast(field.shape).width)

            if field.access.readable():
                m.d.comb += [
                    self.element.r_data[field_slice].eq(field.port.r_data),
                    field.port.r_stb.eq(self.element.r_stb),
                ]
            if field.access.writable():
                m.d.comb += [
                    field.port.w_data.eq(self.element.w_data[field_slice]),
                    field.port.w_stb .eq(self.element.w_stb),
                ]

            field_start = field_slice.stop

        return m


class RegisterMap:
    """A collection of CSR registers."""
    def __init__(self):
        self._registers = dict()
        self._clusters  = dict()
        self._namespace = dict()
        self._frozen    = False

    def freeze(self):
        """Freeze the cluster.

        Once the cluster is frozen, its visible state becomes immutable. Registers and clusters
        cannot be added anymore.
        """
        self._frozen = True

    def add_register(self, register, *, name):
        """Add a register.

        Arguments
        ---------
        register : :class:`Register`
            Register.
        name : :class:`str`
            Name of the register.

        Returns
        -------
        :class:`Register`
            ``register``, which is added to the register map.

        Raises
        ------
        :exc:`ValueError`
            If the register map is frozen.
        :exc:`TypeError`
            If ``register` is not an instance of :class:`Register`.
        :exc:`TypeError`
            If ``name`` is not a string.
        :exc:`ValueError`
            If ``name`` is already used.
        """
        if self._frozen:
            raise ValueError("Register map is frozen")
        if not isinstance(register, Register):
            raise TypeError("Register must be an instance of csr.Register, not {!r}"
                            .format(register))

        if not isinstance(name, str) or not name:
            raise TypeError("Name must be a non-empty string, not {!r}".format(name))
        if name in self._namespace:
            raise ValueError("Name '{}' is already used by {!r}".format(name, self._namespace[name]))

        self._registers[id(register)] = register, name
        self._namespace[name] = register
        return register

    def registers(self):
        """Iterate local registers.

        Yields
        ------
        :class:`Register`
            Register.
        :class:`str`
            Name of the register.
        """
        for register, name in self._registers.values():
            yield register, name

    def add_cluster(self, cluster, *, name):
        """Add a cluster of registers.

        Arguments
        ---------
        cluster : :class:`RegisterMap`
            Cluster of registers.
        name : :class:`str`
            Name of the cluster.

        Returns
        -------
        :class:`RegisterMap`
            ``cluster``, which is added to the register map.

        Raises
        ------
        :exc:`ValueError`
            If the register map is frozen.
        :exc:`TypeError`
            If ``cluster` is not an instance of :class:`RegisterMap`.
        :exc:`TypeError`
            If ``name`` is not a string.
        :exc:`ValueError`
            If ``name`` is already used.
        """
        if self._frozen:
            raise ValueError("Register map is frozen")
        if not isinstance(cluster, RegisterMap):
            raise TypeError("Cluster must be an instance of csr.RegisterMap, not {!r}"
                            .format(cluster))

        if not isinstance(name, str) or not name:
            raise TypeError("Name must be a non-empty string, not {!r}".format(name))
        if name in self._namespace:
            raise ValueError("Name '{}' is already used by {!r}".format(name, self._namespace[name]))

        self._clusters[id(cluster)] = cluster, name
        self._namespace[name] = cluster
        return cluster

    def clusters(self):
        """Iterate local clusters of registers.

        Yields
        ------
        :class:`RegisterMap`
            Cluster of registers.
        :class:`str`
            Name of the cluster.
        """
        for cluster, name in self._clusters.values():
            yield cluster, name

    def flatten(self, *, _path=()):
        """Recursively iterate over all registers.

        Yields
        ------
        :class:`Register`
            Register.
        iter(:class:`str`)
            Path of the register. It contains its name, prefixed by the name of parent clusters up
            to this register map.
        """
        for name, assignment in self._namespace.items():
            path = (*_path, name)
            if id(assignment) in self._registers:
                yield assignment, path
            elif id(assignment) in self._clusters:
                yield from assignment.flatten(_path=path)
            else:
                assert False # :nocov:

    def get_path(self, register, *, _path=()):
        """Get the path of a register.

        Arguments
        ---------
        register : :class:`Register`
            A register of the register map.

        Returns
        -------
        iter(:class:`str`)
            Path of the register. It contains its name, prefixed by the name of parent clusters up
            to this register map.

        Raises
        ------
        :exc:`TypeError`
            If ``register` is not an instance of :class:`Register`.
        :exc:`KeyError`
            If ``register` is not in the register map.
        """
        if not isinstance(register, Register):
            raise TypeError("Register must be an instance of csr.Register, not {!r}"
                            .format(register))

        if id(register) in self._registers:
            _, name = self._registers[id(register)]
            return (*_path, name)

        for cluster, name in self._clusters.values():
            try:
                return cluster.get_path(register, _path=(*_path, name))
            except KeyError:
                pass

        raise KeyError(register)

    def get_register(self, path):
        """Get a register.

        Arguments
        ---------
        path : iter(:class:`str`)
            Path of the register. It contains its name, prefixed by the name of parent clusters up
            to this register map.

        Returns
        -------
        :class:`Register`
            The register assigned to ``path``.

        Raises
        ------
        :exc:`ValueError`
            If ``path`` is empty.
        :exc:`TypeError`
            If ``path`` is not composed of non-empty strings.
        :exc:`KeyError`
            If ``path`` is not assigned to a register.
        """
        path = tuple(path)
        if not path:
            raise ValueError("Path must be a non-empty iterable")
        for name in path:
            if not isinstance(name, str) or not name:
                raise TypeError("Path must contain non-empty strings, not {!r}".format(name))

        name, *rest = path

        if name in self._namespace:
            assignment = self._namespace[name]
            if not rest:
                assert id(assignment) in self._registers
                return assignment
            else:
                assert id(assignment) in self._clusters
                try:
                    return assignment.get_register(rest)
                except KeyError:
                    pass

        raise KeyError(path)


class Bridge(Elaboratable):
    """CSR bridge.

    Parameters
    ----------
    register_map : :class:`RegisterMap`
        Register map.
    addr_width : :class:`int`
        Address width. See :class:`Interface`.
    data_width : :class:`int`
        Data width. See :class:`Interface`.
    alignment : log2 of :class:`int`
        Register alignment. Optional, defaults to ``0``. See :class:`..memory.MemoryMap`.
    name : :class:`str`
        Window name. Optional.
    register_addr : :class:`dict`
        Register address mapping. Optional, defaults to ``None``.
    register_alignment : :class:`dict`
        Register alignment mapping. Optional, defaults to ``None``.

    Attributes
    ----------
    register_map : :class:`RegisterMap`
        Register map.
    bus : :class:`Interface`
        CSR bus providing access to registers.

    Raises
    ------
    :exc:`TypeError`
        If ``register_map`` is not an instance of :class:`RegisterMap`.
    :exc:`TypeError`
        If ``register_addr`` is a not a mapping.
    :exc:`TypeError`
        If ``register_alignment`` is a not a mapping.
    """
    def __init__(self, register_map, *, addr_width, data_width, alignment=0, name=None,
                 register_addr=None, register_alignment=None):
        if not isinstance(register_map, RegisterMap):
            raise TypeError("Register map must be an instance of RegisterMap, not {!r}"
                            .format(register_map))

        memory_map = MemoryMap(addr_width=addr_width, data_width=data_width, alignment=alignment,
                               name=name)

        def get_register_param(path, root, kind):
            node = root
            prev = []
            for name in path:
                if node is None:
                    break
                if not isinstance(node, Mapping):
                    raise TypeError("Register {}{} must be a mapping, not {!r}"
                                    .format(kind, "" if not prev else f" {tuple(prev)}", node))
                prev.append(name)
                node = node.get(name, None)
            return node

        register_map.freeze()

        for register, path in register_map.flatten():
            elem_size = (register.element.width + data_width - 1) // data_width
            elem_name = "__".join(path)
            elem_addr = get_register_param(path, register_addr, "address")
            elem_alignment = get_register_param(path, register_alignment, "alignment")
            memory_map.add_resource(register.element, name=elem_name, size=elem_size,
                                    addr=elem_addr, alignment=elem_alignment)

        self._map = register_map
        self._mux = Multiplexer(memory_map)

    @property
    def register_map(self):
        return self._map

    @property
    def bus(self):
        return self._mux.bus

    def elaborate(self, platform):
        m = Module()
        for register, path in self.register_map.flatten():
            m.submodules["__".join(path)] = register
        m.submodules.mux = self._mux
        return m
