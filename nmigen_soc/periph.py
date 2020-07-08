from .memory import MemoryMap
from . import event


__all__ = ["PeripheralInfo"]


class PeripheralInfo:
    """Peripheral metadata.

    A unified description of the local resources of a peripheral. It may be queried in order to
    recover its memory windows, CSR registers and event sources.

    Parameters
    ----------
    memory_map : :class:`MemoryMap`
        Memory map of the peripheral.
    irq : :class:`event.Source`
        IRQ line of the peripheral. Optional.
    """
    def __init__(self, *, memory_map, irq=None):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError("Memory map must be an instance of MemoryMap, not {!r}"
                            .format(memory_map))
        memory_map.freeze()
        self._memory_map = memory_map

        if irq is not None and not isinstance(irq, event.Source):
            raise TypeError("IRQ line must be an instance of event.Source, not {!r}"
                            .format(irq))
        self._irq = irq

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
            raise NotImplementedError("Peripheral info does not have an IRQ line"
                                      .format(self))
        return self._irq
