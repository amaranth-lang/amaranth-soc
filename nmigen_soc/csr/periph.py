from nmigen import *
from nmigen import tracer

from .bus import *


__all__ = ["Peripheral", "IRQLine", "Event", "PeripheralBridge"]


class Peripheral:
    """CSR-capable peripheral.

    A helper class to reduce the boilerplate needed to control a peripheral with a CSR interface.
    It provides facilities for instantiating CSR registers and sending interrupt requests to the
    CPU.

    The ``Peripheral`` class is not meant to be instantiated as-is, but rather as a base class for
    actual peripherals.

    Usage example
    -------------

    ```
    class ExamplePeripheral(csr.Peripheral, Elaboratable):
        def __init__(self):
            super().__init__()
            self._data   = self.csr(8, "w")
            self._rdy    = self.event(mode="rise")

            self._bridge = self.csr_bridge()
            self.csr_bus = self._bridge.bus
            self.irq     = self._bridge.irq

        def elaborate(self, platform):
            m = Module()
            m.submodules.bridge = self._bridge
            # ...
            return m
    ```

    Parameters
    ----------
    name : str
        Name of this peripheral. If ``None`` (default) the name is inferred from the variable
        name this peripheral is assigned to.

    Attributes
    ----------
    name : str
        Name of the peripheral.
    """
    def __init__(self, name=None, src_loc_at=1):
        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}".format(name))
        self.name      = name or tracer.get_var_name(depth=2 + src_loc_at)

        self._csr_regs = []
        self._csr_bus  = None

        self._events   = []
        self._irq      = None

    @property
    def csr_bus(self):
        """CSR bus providing access to registers.

        Return value
        ------------
        An instance of :class:`Interface`.

        Exceptions
        ----------
        Raises :exn:`NotImplementedError` if the peripheral does not have a CSR bus.
        """
        if self._csr_bus is None:
            raise NotImplementedError("Peripheral {!r} does not have a CSR bus interface"
                                      .format(self))
        return self._csr_bus

    @csr_bus.setter
    def csr_bus(self, csr_bus):
        if not isinstance(csr_bus, Interface):
            raise TypeError("CSR bus interface must be an instance of csr.Interface, not {!r}"
                            .format(csr_bus))
        self._csr_bus = csr_bus

    @property
    def irq(self):
        """Interrupt request line.

        Return value
        ------------
        An instance of :class:`IRQLine`.

        Exceptions
        ----------
        Raises :exn:`NotImplementedError` if the peripheral does not have an IRQ line.
        """
        if self._irq is None:
            raise NotImplementedError("Peripheral {!r} does not have an IRQ line"
                                      .format(self))
        return self._irq

    @irq.setter
    def irq(self, irq):
        if not isinstance(irq, IRQLine):
            raise TypeError("IRQ line must be an instance of IRQLine, not {!r}"
                            .format(irq))
        self._irq = irq

    def csr(self, width, access, *, addr=None, alignment=0, name=None, src_loc_at=0):
        """Request a CSR register.

        Parameters
        ----------
        width : int
            Width of the register. See :class:`Element`.
        access : :class:`Access`
            Register access mode. See :class:`Element`.
        addr : int
            Address of the register. See :meth:`Multiplexer.add`.
        alignment : int
            Register alignment. See :class:`Multiplexer`.
        name : str
            Name of the register. If ``None`` (default) the name is inferred from the variable
            name this register is assigned to.

        Return value
        ------------
        An instance of :class:`Element`.
        """
        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}".format(name))
        elem_name = name or tracer.get_var_name(depth=2 + src_loc_at)

        elem = Element(width, access, name="{}_{}".format(self.name, elem_name))
        self._csr_regs.append((elem, addr, alignment))
        return elem

    def event(self, *, mode="level", name=None, src_loc_at=0):
        """Request an event source.

        See :class:`Event` for details.

        Return value
        ------------
        An instance of :class:`Event`.
        """
        event = Event(mode=mode, name=name, src_loc_at=1 + src_loc_at)
        self._events.append(event)
        return event

    def csr_bridge(self, *, data_width=8, alignment=0):
        """Request a bridge to the resources of the peripheral.

        See :class:`PeripheralBridge` for details.

        Return value
        ------------
        An instance of :class:`PeripheralBridge` providing access to the registers
        of the peripheral and managing its event sources.
        """
        return PeripheralBridge(self, data_width=data_width, alignment=alignment)

    def csr_registers(self):
        """Iterate requested CSR registers and their parameters.

        Yield values
        ------------
        A tuple ``elem, addr, alignment`` describing the register and its parameters.
        """
        for elem, addr, alignment in self._csr_regs:
            yield elem, addr, alignment

    def events(self):
        """Iterate requested event sources.

        Event sources are ordered by request order.

        Yield values
        ------------
        An instance of :class:`Event`.
        """
        for event in self._events:
            yield event


class IRQLine(Signal):
    """Interrupt request line."""
    def __init__(self, *, name=None, src_loc_at=0):
        super().__init__(name=name, src_loc_at=1 + src_loc_at)


class Event:
    """Event source.

    Parameters
    ----------
    mode : ``"level"``, ``"rise"``, ``"fall"``
        Trigger mode. If ``"level"``, a notification is raised when the ``stb`` signal is high.
        If ``"rise"`` (or ``"fall"``) a notification is raised on a rising (or falling) edge
        of ``stb``.
    name : str
        Name of the event. If ``None`` (default) the name is inferred from the variable
        name this event source is assigned to.

    Attributes
    ----------
    name : str
        Name of the event
    mode : ``"level"``, ``"rise"``, ``"fall"``
        Trigger mode.
    stb : Signal, in
        Event strobe.
    """
    def __init__(self, *, mode, name=None, src_loc_at=0):
        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}".format(name))

        choices = ("level", "rise", "fall")
        if mode not in choices:
            raise ValueError("Invalid trigger mode {!r}; must be one of {}"
                             .format(mode, ", ".join(choices)))

        self.name = name or tracer.get_var_name(depth=2 + src_loc_at)
        self.mode = mode
        self.stb  = Signal(name="{}_stb".format(self.name))


class PeripheralBridge(Elaboratable):
    """Peripheral bridge.

    A bridge providing access to the registers of a peripheral, and support for interrupt
    requests (IRQs) from its event sources.

    CSR registers
    -------------
    ev_status : read-only
        Event status. Each bit displays the value of the ``stb`` signal of an event source.
        The register width is ``len(list(periph.events())`` bits. Event sources are ordered by
        request order.
    ev_pending : read/write
        Event pending. Each bit displays whether an event source has a pending notification.
        Writing 1 to a bit clears the notification.
        The register width is ``len(list(periph.events())`` bits. Event sources are ordered by
        request order.
    ev_enable : read/write
        Event enable. Writing 1 to a bit enables an event source. Writing 0 disables it.
        The register width is ``len(list(periph.events())`` bits. Event sources are ordered by
        request order.

    Parameters
    ----------
    periph : :class:`Peripheral`
        The peripheral whose resources are exposed by this bridge.
    data_width : int
        Data width of the CSR bus. See :class:`Multiplexer`.
    alignment : int
        Register alignment. See :class:`Multiplexer`.

    Attributes
    ----------
    bus : :class:`Interface`
        CSR bus providing access to the registers of the peripheral.
    irq : :class:`IRQLine` or None
        IRQ line providing notifications from local events to the CPU. It is raised if any
        event source is both enabled and has a pending notification. If the peripheral has
        no event sources, it is set to ``None``.
    """
    def __init__(self, periph, *, data_width, alignment):
        if not isinstance(periph, Peripheral):
            raise TypeError("Peripheral must be an instance of Peripheral, not {!r}"
                            .format(periph))

        self._mux = Multiplexer(addr_width=1, data_width=data_width, alignment=alignment)
        for elem, elem_addr, elem_alignment in periph.csr_registers():
            self._mux.add(elem, addr=elem_addr, alignment=elem_alignment, extend=True)

        self._events = list(periph.events())
        if len(self._events) > 0:
            width = len(self._events)
            self._ev_status  = Element(width, "r",  name="{}_ev_status".format(periph.name))
            self._ev_pending = Element(width, "rw", name="{}_ev_pending".format(periph.name))
            self._ev_enable  = Element(width, "rw", name="{}_ev_enable".format(periph.name))
            self._mux.add(self._ev_status,  extend=True)
            self._mux.add(self._ev_pending, extend=True)
            self._mux.add(self._ev_enable,  extend=True)
            self.irq = IRQLine(name="{}_irq".format(periph.name))
        else:
            self.irq = None

        self.bus = self._mux.bus

    def elaborate(self, platform):
        m = Module()

        m.submodules.mux = self._mux

        if self.irq is not None:
            with m.If(self._ev_pending.w_stb):
                m.d.sync += self._ev_pending.r_data.eq(   self._ev_pending.r_data
                                                       & ~self._ev_pending.w_data)
            with m.If(self._ev_enable.w_stb):
                m.d.sync += self._ev_enable.r_data.eq(self._ev_enable.w_data)

            for i, ev in enumerate(self._events):
                m.d.sync += self._ev_status.r_data[i].eq(ev.stb)

                if ev.mode in ("rise", "fall"):
                    ev_stb_r = Signal.like(ev.stb, name_suffix="_r")
                    m.d.sync += ev_stb_r.eq(ev.stb)

                ev_trigger = Signal(name="{}_trigger".format(ev.name))
                if ev.mode == "level":
                    m.d.comb += ev_trigger.eq(ev.stb)
                elif ev.mode == "rise":
                    m.d.comb += ev_trigger.eq(~ev_stb_r &  ev.stb)
                elif ev.mode == "fall":
                    m.d.comb += ev_trigger.eq( ev_stb_r & ~ev.stb)
                else:
                    assert False # :nocov:

                with m.If(ev_trigger):
                    m.d.sync += self._ev_pending.r_data[i].eq(1)

            m.d.comb += self.irq.eq((self._ev_pending.r_data & self._ev_enable.r_data).any())

        return m
