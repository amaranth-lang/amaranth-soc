from collections import OrderedDict
from collections.abc import Mapping

from amaranth.utils import bits_for

from .memory import MemoryMap
from . import event


__all__ = ["ConstantValue", "ConstantBool", "ConstantInt", "ConstantMap", "PeripheralInfo"]


class ConstantValue:
    pass


class ConstantBool(ConstantValue):
    """Boolean constant.

    Parameters
    ----------
    value : bool
        Constant value.
    """
    def __init__(self, value):
        if not isinstance(value, bool):
            raise TypeError(f"Value must be a bool, not {value!r}")
        self._value = value

    @property
    def value(self):
        return self._value

    def __repr__(self):
        return f"ConstantBool({self.value})"


class ConstantInt(ConstantValue):
    """Integer constant.

    Parameters
    ----------
    value : int
        Constant value.
    width : int
        Width in bits. Optional. ``bits_for(value)`` by default.
    signed : bool
        Signedness. Optional. ``value < 0`` by default.
    """
    def __init__(self, value, *, width=None, signed=None):
        if not isinstance(value, int):
            raise TypeError(f"Value must be an integer, not {value!r}")
        self._value = value

        if width is None:
            width = bits_for(value)
        if not isinstance(width, int):
            raise TypeError(f"Width must be an integer, not {width!r}")
        if width < bits_for(value):
            raise ValueError(f"Width must be greater than or equal to the number of bits needed "
                             f"to represent {value}")
        self._width = width

        if signed is None:
            signed = value < 0
        if not isinstance(signed, bool):
            raise TypeError(f"Signedness must be a bool, not {signed!r}")
        self._signed = signed

    @property
    def value(self):
        return self._value

    @property
    def width(self):
        return self._width

    @property
    def signed(self):
        return self._signed

    def __repr__(self):
        return f"ConstantInt({self.value}, width={self.width}, signed={self.signed})"


class ConstantMap(Mapping):
    """Named constant map.

    A read-only container for named constants. Keys are iterated in insertion order.

    Parameters
    ----------
    **constants : dict(str : :class:`ConstantValue`)
        Named constants.

    Examples
    --------
    >>> ConstantMap(RX_FIFO_DEPTH=16)
    ConstantMap([('RX_FIFO_DEPTH', ConstantInt(16, width=5, signed=False))])
    """
    def __init__(self, **constants):
        self._storage = OrderedDict()
        for key, value in constants.items():
            if isinstance(value, bool):
                value = ConstantBool(value)
            if isinstance(value, int):
                value = ConstantInt(value)
            if not isinstance(value, ConstantValue):
                raise TypeError(f"Constant value must be an instance of ConstantValue, not "
                                f"{value!r}")
            self._storage[key] = value

    def __getitem__(self, key):
        return self._storage[key]

    def __iter__(self):
        yield from self._storage

    def __len__(self):
        return len(self._storage)

    def __repr__(self):
        return f"ConstantMap({list(self._storage.items())})"


class PeripheralInfo:
    """Peripheral metadata.

    A unified description of the local resources of a peripheral. It may be queried in order to
    recover its memory windows, CSR registers, event sources and configuration constants.

    Parameters
    ----------
    memory_map : :class:`MemoryMap`
        Memory map of the peripheral.
    irq : :class:`event.Source`
        IRQ line of the peripheral. Optional.
    constant_map : :class:`ConstantMap`
        Constant map of the peripheral. Optional.
    """
    def __init__(self, *, memory_map, irq=None, constant_map=None):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"Memory map must be an instance of MemoryMap, not {memory_map!r}")
        memory_map.freeze()
        self._memory_map = memory_map

        if irq is not None and not isinstance(irq, event.Source):
            raise TypeError(f"IRQ line must be an instance of event.Source, not {irq!r}")
        self._irq = irq

        if constant_map is None:
            constant_map = ConstantMap()
        if not isinstance(constant_map, ConstantMap):
            raise TypeError(f"Constant map must be an instance of ConstantMap, not "
                            f"{constant_map!r}")
        self._constant_map = constant_map

    @property
    def memory_map(self):
        """Memory map.

        Return value
        ------------
        A :class:`MemoryMap` describing the local address space of the peripheral.
        """
        return self._memory_map

    @property
    def irq(self):
        """IRQ line.

        Return value
        ------------
        An :class:`event.Source` used by the peripheral to request interrupts. If provided, its
        event map describes local events.

        Exceptions
        ----------
        Raises :exn:`NotImplementedError` if the peripheral info does not have an IRQ line.
        """
        if self._irq is None:
            raise NotImplementedError("Peripheral info does not have an IRQ line")
        return self._irq

    @property
    def constant_map(self):
        """Constant map.

        Return value
        ------------
        A :class:`ConstantMap` containing configuration constants of the peripheral.
        """
        return self._constant_map
