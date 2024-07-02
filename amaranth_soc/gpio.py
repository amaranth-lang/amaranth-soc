from amaranth import *
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out, flipped, connect

from . import csr


__all__ = ["PinMode", "PinSignature", "Peripheral"]


class PinMode(enum.Enum, shape=unsigned(2)):
    """GPIO pin mode.

    The 2-bit values of this enumeration can be written to a :class:`Peripheral.Mode` field to
    configure the pins of a :class:`Peripheral`.
    """

    #: `Input-only` mode.
    #:
    #: The pin output is disabled but remains connected to its :class:`Peripheral.Output` field.
    #: Its :attr:`Peripheral.alt_mode` bit is wired to 0.
    INPUT_ONLY = 0b00

    #: `Push-pull` mode.
    #:
    #: The pin output is enabled and connected to its :class:`Peripheral.Output` field. Its
    #: :attr:`Peripheral.alt_mode` bit is wired to 0.
    PUSH_PULL = 0b01

    #: `Open-drain` mode.
    #:
    #: The pin output is enabled when the value of its :class:`Peripheral.Output` field is 0, and
    #: is itself wired to 0. Its :attr:`Peripheral.alt_mode` bit is wired to 0.
    OPEN_DRAIN = 0b10

    #: `Alternate` mode.
    #:
    #: The pin output is disabled but remains connected to its :class:`Peripheral.Output` field.
    #: Its :attr:`Peripheral.alt_mode` bit is wired to 1.
    ALTERNATE = 0b11


class PinSignature(wiring.Signature):
    """GPIO pin signature.

    Interface attributes
    --------------------
    i : :class:`Signal`
        Input.
    o : :class:`Signal`
        Output.
    oe : :class:`Signal`
        Output enable.
    """
    def __init__(self):
        super().__init__({
            "i":  In(unsigned(1)),
            "o":  Out(unsigned(1)),
            "oe": Out(unsigned(1)),
        })


class Peripheral(wiring.Component):
    class Mode(csr.Register, access="rw"):
        """Mode register.

        This :class:`csr.Register` contains an array of ``pin_count`` read/write fields. Each field
        is 2-bit wide and its possible values are defined by the :class:`PinMode` enumeration.

        If ``pin_count`` is 8, then the register has the following fields:

        .. bitfield::
            :bits: 16

                [
                    { "name": "pin[0]", "bits": 2, "attr": "RW" },
                    { "name": "pin[1]", "bits": 2, "attr": "RW" },
                    { "name": "pin[2]", "bits": 2, "attr": "RW" },
                    { "name": "pin[3]", "bits": 2, "attr": "RW" },
                    { "name": "pin[4]", "bits": 2, "attr": "RW" },
                    { "name": "pin[5]", "bits": 2, "attr": "RW" },
                    { "name": "pin[6]", "bits": 2, "attr": "RW" },
                    { "name": "pin[7]", "bits": 2, "attr": "RW" },
                ]

        Parameters
        ----------
        pin_count : :class:`int`
            Number of GPIO pins.
        """
        def __init__(self, pin_count):
            super().__init__({
                "pin": [csr.Field(csr.action.RW, PinMode) for _ in range(pin_count)],
            })

    class Input(csr.Register, access="r"):
        """Input register.

        This :class:`csr.Register` contains an array of ``pin_count`` read-only fields. Each field
        is 1-bit wide and driven by the input of its associated pin in the :attr:`Peripheral.pins`
        array.

        Values sampled from pin inputs go through :attr:`Peripheral.input_stages` synchronization
        stages (on a rising edge of ``ClockSignal("sync")``) before reaching the register.

        If ``pin_count`` is 8, then the register has the following fields:

        .. bitfield::
            :bits: 8

                [
                    { "name": "pin[0]", "bits": 1, "attr": "R" },
                    { "name": "pin[1]", "bits": 1, "attr": "R" },
                    { "name": "pin[2]", "bits": 1, "attr": "R" },
                    { "name": "pin[3]", "bits": 1, "attr": "R" },
                    { "name": "pin[4]", "bits": 1, "attr": "R" },
                    { "name": "pin[5]", "bits": 1, "attr": "R" },
                    { "name": "pin[6]", "bits": 1, "attr": "R" },
                    { "name": "pin[7]", "bits": 1, "attr": "R" },
                ]

        Parameters
        ----------
        pin_count : :class:`int`
            Number of GPIO pins.
        """
        def __init__(self, pin_count):
            super().__init__({
                "pin": [csr.Field(csr.action.R, unsigned(1)) for _ in range(pin_count)],
            })

    class Output(csr.Register, access="rw"):
        """Output register.

        This :class:`csr.Register` contains an array of ``pin_count`` read/write fields. Each field
        is 1-bit wide and drives the output of its associated pin in the :attr:`Peripheral.pins`
        array, depending on its associated :class:`~Peripheral.Mode` field.

        If ``pin_count`` is 8, then the register has the following fields:

        .. bitfield::
            :bits: 8

                [
                    { "name": "pin[0]", "bits": 1, "attr": "RW" },
                    { "name": "pin[1]", "bits": 1, "attr": "RW" },
                    { "name": "pin[2]", "bits": 1, "attr": "RW" },
                    { "name": "pin[3]", "bits": 1, "attr": "RW" },
                    { "name": "pin[4]", "bits": 1, "attr": "RW" },
                    { "name": "pin[5]", "bits": 1, "attr": "RW" },
                    { "name": "pin[6]", "bits": 1, "attr": "RW" },
                    { "name": "pin[7]", "bits": 1, "attr": "RW" },
                ]

        Parameters
        ----------
        pin_count : :class:`int`
            Number of GPIO pins.
        """
        class _FieldAction(csr.FieldAction):
            def __init__(self):
                super().__init__(shape=unsigned(1), access="rw", members=(
                    ("data", Out(unsigned(1))),
                    ("set",  In(unsigned(1))),
                    ("clr",  In(unsigned(1))),
                ))
                self._storage = Signal(unsigned(1))

            def elaborate(self, platform):
                m = Module()

                with m.If(self.set != self.clr):
                    m.d.sync += self._storage.eq(self.set)
                with m.Elif(self.port.w_stb):
                    m.d.sync += self._storage.eq(self.port.w_data)

                m.d.comb += [
                    self.port.r_data.eq(self._storage),
                    self.data.eq(self._storage),
                ]

                return m

        def __init__(self, pin_count):
            super().__init__({
                "pin": [csr.Field(self._FieldAction) for _ in range(pin_count)],
            })

    class SetClr(csr.Register, access="w"):
        """Output set/clear register.

        This :class:`csr.Register` contains an array of ``pin_count`` write-only fields. Each field
        is 2-bit wide; writing it can modify its associated :class:`~Peripheral.Output` field as a
        side-effect.

        If ``pin_count`` is 8, then the register has the following fields:

        .. bitfield::
            :bits: 16

                [
                    { "name": "pin[0]", "bits": 2, "attr": "W" },
                    { "name": "pin[1]", "bits": 2, "attr": "W" },
                    { "name": "pin[2]", "bits": 2, "attr": "W" },
                    { "name": "pin[3]", "bits": 2, "attr": "W" },
                    { "name": "pin[4]", "bits": 2, "attr": "W" },
                    { "name": "pin[5]", "bits": 2, "attr": "W" },
                    { "name": "pin[6]", "bits": 2, "attr": "W" },
                    { "name": "pin[7]", "bits": 2, "attr": "W" },
                ]

        - Writing `0b01` to a field sets its associated :class:`~Peripheral.Output` field.
        - Writing `0b10` to a field clears its associated :class:`~Peripheral.Output` field.
        - Writing `0b00` or `0b11` to a field has no side-effect.

        Parameters
        ----------
        pin_count : :class:`int`
            Number of GPIO pins.
        """
        def __init__(self, pin_count):
            pin_fields = {
                "set": csr.Field(csr.action.W, unsigned(1)),
                "clr": csr.Field(csr.action.W, unsigned(1)),
            }
            super().__init__({
                "pin": [pin_fields for _ in range(pin_count)],
            })

    """GPIO peripheral.

    Parameters
    ----------
    pin_count : :class:`int`
        Number of GPIO pins.
    addr_width : :class:`int`
        CSR bus address width.
    data_width : :class:`int`
        CSR bus data width.
    input_stages : :class:`int`
        Number of synchronization stages between pin inputs and the :class:`~Peripheral.Input`
        register. Optional. Defaults to ``2``.

    Attributes
    ----------
    bus : :class:`csr.Interface`
        CSR bus interface providing access to registers.
    pins : :class:`list` of :class:`wiring.PureInterface` of :class:`PinSignature`
        GPIO pin interfaces.
    alt_mode : :class:`Signal`
        Indicates which members of the :attr:`Peripheral.pins` array are in alternate mode.

    Raises
    ------
    :exc:`TypeError`
        If ``pin_count`` is not a positive integer.
    :exc:`TypeError`
        If ``input_stages`` is not a non-negative integer.
    """
    def __init__(self, *, pin_count, addr_width, data_width, input_stages=2):
        if not isinstance(pin_count, int) or pin_count <= 0:
            raise TypeError(f"Pin count must be a positive integer, not {pin_count!r}")
        if not isinstance(input_stages, int) or input_stages < 0:
            raise TypeError(f"Input stages must be a non-negative integer, not {input_stages!r}")

        regs = csr.Builder(addr_width=addr_width, data_width=data_width)

        self._mode   = regs.add("Mode",   self.Mode(pin_count))
        self._input  = regs.add("Input",  self.Input(pin_count))
        self._output = regs.add("Output", self.Output(pin_count))
        self._setclr = regs.add("SetClr", self.SetClr(pin_count))

        self._bridge = csr.Bridge(regs.as_memory_map())

        super().__init__({
            "bus":      In(csr.Signature(addr_width=addr_width, data_width=data_width)),
            "pins":     Out(PinSignature()).array(pin_count),
            "alt_mode": Out(unsigned(pin_count)),
        })
        self.bus.memory_map = self._bridge.bus.memory_map

        self._pin_count    = pin_count
        self._input_stages = input_stages

    @property
    def pin_count(self):
        """Number of GPIO pins.

        Returns
        -------
        :class:`int`
        """
        return self._pin_count

    @property
    def input_stages(self):
        """Number of synchronization stages between pin inputs and the :class:`~Peripheral.Input`
        register.

        Returns
        -------
        :class:`int`
        """
        return self._input_stages

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge = self._bridge

        connect(m, flipped(self.bus), self._bridge.bus)

        for n, pin in enumerate(self.pins):
            pin_i_sync = pin.i
            for stage in range(self.input_stages):
                pin_i_sync_ff = Signal(reset_less=True, name=f"pin_{n}_i_sync_ff_{stage}")
                m.d.sync += pin_i_sync_ff.eq(pin_i_sync)
                pin_i_sync = pin_i_sync_ff
                del pin_i_sync_ff

            m.d.comb += self._input.f.pin[n].r_data.eq(pin_i_sync)

            with m.If(self._setclr.f.pin[n].set.w_stb & self._setclr.f.pin[n].set.w_data):
                m.d.comb += self._output.f.pin[n].set.eq(1)
            with m.If(self._setclr.f.pin[n].clr.w_stb & self._setclr.f.pin[n].clr.w_data):
                m.d.comb += self._output.f.pin[n].clr.eq(1)

            with m.Switch(self._mode.f.pin[n].data):
                with m.Case(PinMode.INPUT_ONLY):
                    m.d.comb += [
                        pin.o .eq(self._output.f.pin[n].data),
                        pin.oe.eq(0),
                    ]
                with m.Case(PinMode.PUSH_PULL):
                    m.d.comb += [
                        pin.o .eq(self._output.f.pin[n].data),
                        pin.oe.eq(1),
                    ]
                with m.Case(PinMode.OPEN_DRAIN):
                    m.d.comb += [
                        pin.o .eq(0),
                        pin.oe.eq(~self._output.f.pin[n].data),
                    ]
                with m.Case(PinMode.ALTERNATE):
                    m.d.comb += [
                        pin.o .eq(self._output.f.pin[n].data),
                        pin.oe.eq(0),
                    ]
                    m.d.comb += self.alt_mode[n].eq(1)

        return m
