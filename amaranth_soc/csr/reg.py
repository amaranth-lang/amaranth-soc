from collections.abc import Mapping, Sequence
from amaranth import *
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from ..memory import MemoryMap
from .bus import Element, Signature, Multiplexer


__all__ = [
    "FieldPort", "Field", "FieldAction", "FieldActionMap", "FieldActionArray",
    "Register", "RegisterMap",
    "Bridge",
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
        shape : :ref:`shape-castable <lang-shapecasting>`
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

        Raises
        ------
        See :meth:`FieldPort.Signature.check_parameters`.
        """
        def __init__(self, shape, access):
            self.check_parameters(shape, access)
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

        @classmethod
        def check_parameters(cls, shape, access):
            """Validate signature parameters.

            Raises
            ------
            :exc:`TypeError`
                If ``shape`` is not a shape-castable object.
            :exc:`ValueError`
                If ``access`` is not a member of :class:`FieldPort.Access`.
            """
            try:
                Shape.cast(shape)
            except TypeError as e:
                raise TypeError(f"Field shape must be a shape-castable object, not {shape!r}") from e
            # TODO(py3.9): Remove this. Python 3.8 and below use cls.__name__ in the error message
            # instead of cls.__qualname__.
            # FieldPort.Access(access)
            try:
                FieldPort.Access(access)
            except ValueError as e:
                raise ValueError(f"{access!r} is not a valid FieldPort.Access") from e

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
    shape : :ref:`shape-castable <lang-shapecasting>`
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
    shape : :ref:`shape-castable <lang-shapecasting>`
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
    fields : :class:`dict` or :class:`list`
        Collection of register fields. If ``None`` (default), a dict is populated from Python
        :term:`variable annotations <python:variable annotations>`. ``fields`` is used to populate
        a :class:`FieldActionMap` or a :class:`FieldActionArray`, depending on its type (dict or
        list).
    {parameters}

    Interface attributes
    --------------------
    element : :class:`Element`
        Interface between this register and a CSR bus primitive.

    Attributes
    ----------
    fields : :class:`FieldActionMap` or :class:`FieldActionArray`
        Collection of field instances.
    f : :class:`FieldActionMap` or :class:`FieldActionArray`
        Shorthand for :attr:`Register.fields`.

    Raises
    ------
    :exc:`TypeError`
        If ``fields`` is neither ``None``, a :class:`dict` or a :class:`list`.
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
            # TODO(py3.9): Remove this. Python 3.8 and below use cls.__name__ in the error message
            # instead of cls.__qualname__.
            # cls._access = Element.Access(access)
            try:
                cls._access = Element.Access(access)
            except ValueError as e:
                raise ValueError(f"{access!r} is not a valid Element.Access") from e
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
            self._fields = FieldActionMap(fields)
        elif isinstance(fields, list):
            self._fields = FieldActionArray(fields)
        else:
            raise TypeError(f"Field collection must be a dict or a list, not {fields!r}")

        width = 0
        for field_path, field in self._fields.flatten():
            width += Shape.cast(field.port.shape).width
            if field.port.access.readable() and not access.readable():
                raise ValueError(f"Field {'__'.join(field_path)} is readable, but element access "
                                 f"mode is {access}")
            if field.port.access.writable() and not access.writable():
                raise ValueError(f"Field {'__'.join(field_path)} is writable, but element access "
                                 f"mode is {access}")

        super().__init__({"element": Out(Element.Signature(width, access))})

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
            Path of the field. It is prefixed by the name of every nested :class:`FieldActionMap`
            or :class:`FieldActionArray`.
        :class:`FieldAction`
            Field instance.
        """
        yield from self.fields.flatten()

    def elaborate(self, platform):
        m = Module()

        field_start = 0

        for field_path, field in self.fields.flatten():
            field_width = Shape.cast(field.port.shape).width
            field_slice = slice(field_start, field_start + field_width)

            m.submodules["__".join(str(key) for key in field_path)] = field

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
            raise TypeError(f"Register must be an instance of csr.Register, not {register!r}")

        if not isinstance(name, str) or not name:
            raise TypeError(f"Name must be a non-empty string, not {name!r}")
        if name in self._namespace:
            raise ValueError(f"Name '{name}' is already used by {self._namespace[name]!r}")

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
            raise TypeError(f"Cluster must be an instance of csr.RegisterMap, not {cluster!r}")

        if not isinstance(name, str) or not name:
            raise TypeError(f"Name must be a non-empty string, not {name!r}")
        if name in self._namespace:
            raise ValueError(f"Name '{name}' is already used by {self._namespace[name]!r}")

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
            raise TypeError(f"Register must be an instance of csr.Register, not {register!r}")

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
                raise TypeError(f"Path must contain non-empty strings, not {name!r}")

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


class Bridge(wiring.Component):
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
        Register address assignments. Optional, defaults to ``None``.
    register_alignment : :class:`dict`
        Register alignment assignments. Optional, defaults to ``None``.

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
        If ``register_addr`` is a not a dict.
    :exc:`TypeError`
        If ``register_alignment`` is a not a dict.
    """
    def __init__(self, register_map, *, addr_width, data_width, alignment=0, name=None,
                 register_addr=None, register_alignment=None):
        if not isinstance(register_map, RegisterMap):
            raise TypeError(f"Register map must be an instance of RegisterMap, not "
                            f"{register_map!r}")

        memory_map = MemoryMap(addr_width=addr_width, data_width=data_width, alignment=alignment,
                               name=name)

        def traverse_path(path, obj):
            progress = []
            for name in path:
                if not isinstance(obj, dict):
                    break
                progress.append(name)
                obj = obj.get(name, None)
            return obj, tuple(progress)

        register_map.freeze()

        for register, path in register_map.flatten():
            reg_addr, assigned = traverse_path(path, register_addr)
            if assigned != path and reg_addr is not None:
                raise TypeError(f"Register address assignment for the cluster {tuple(assigned)} "
                                f"must be a dict or None, not {reg_addr!r}")

            reg_alignment, assigned = traverse_path(path, register_alignment)
            if assigned != path and reg_alignment is not None:
                raise TypeError(f"Register alignment assignment for the cluster {tuple(assigned)} "
                                f"must be a dict or None, not {reg_alignment!r}")

            reg_size = (register.element.width + data_width - 1) // data_width
            reg_name = "__".join(path)
            memory_map.add_resource(register, name=(reg_name,), size=reg_size, addr=reg_addr,
                                    alignment=reg_alignment)

        self._map = register_map
        self._mux = Multiplexer(memory_map)

        super().__init__({"bus": In(Signature(addr_width=addr_width, data_width=data_width))})
        self.bus.memory_map = self._mux.bus.memory_map

    @property
    def register_map(self):
        return self._map

    def elaborate(self, platform):
        m = Module()

        m.submodules.mux = self._mux
        for register, path in self.register_map.flatten():
            m.submodules["__".join(path)] = register

        connect(m, flipped(self.bus), self._mux.bus)

        return m
