from amaranth import *
from amaranth.lib import stream, wiring
from amaranth.lib.wiring import In, Out, flipped, connect

from . import csr


__all__ = ["RxPhySignature", "TxPhySignature", "RxPeripheral", "TxPeripheral", "Peripheral"]


class RxPhySignature(wiring.Signature):
    """Receiver PHY signature.

    Parameters
    ----------
    phy_config_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the `config` member of this interface.
    symbol_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the `symbols.payload` member of this interface.

    Members
    -------
    rst : :py:`Out(1)`
        PHY reset.
    config : :py:`Out(phy_config_shape)`
        PHY configuration word. Its shape is given by the `phy_config_shape` parameter. Its value
        must remain constant unless `rst` is high.
    symbols : :py:`In(stream.Signature(symbol_shape))`
        Symbol stream. The shape of its payload is given by the `symbol_shape` parameter.
    overflow : :py:`In(1)`
        Overflow flag. Pulsed for one clock cycle if a symbol was received before the previous one
        is acknowledged (i.e. before `symbols.ready` is high).
    error : :py:`In(1)`
        Receiver error flag. Pulsed for one clock cycle in case of an implementation-specific error
        (e.g. wrong parity bit).
    """
    def __init__(self, phy_config_shape, symbol_shape):
        super().__init__({
            "rst":      Out(1),
            "config":   Out(phy_config_shape),
            "symbols":  In(stream.Signature(symbol_shape)),
            "overflow": In(1),
            "error":    In(1),
        })


class TxPhySignature(wiring.Signature):
    """Transmitter PHY signature.

    Parameters
    ----------
    phy_config_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the `config` member of this interface.
    symbol_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the `symbols.payload` member of this interface.

    Members
    -------
    rst : :py:`Out(1)`
        PHY reset.
    config : :py:`Out(phy_config_shape)`
        PHY configuration. Its shape is given by the `phy_config_shape` parameter. Its value must
        remain constant unless `rst` is high.
    symbols : :py:`Out(stream.Signature(symbol_shape))`
        Symbol stream. The shape of its payload is given by the `symbol_shape` parameter.
    """
    def __init__(self, phy_config_shape, symbol_shape):
        super().__init__({
            "rst":     Out(1),
            "config":  Out(phy_config_shape),
            "symbols": Out(stream.Signature(symbol_shape)),
        })


class _PhyConfigFieldAction(csr.FieldAction):
    def __init__(self, shape, *, init=0):
        super().__init__(shape, access="rw", members=(
            ("data", Out(shape)),
            ("w_en", In(unsigned(1))),
        ))
        self._storage = Signal(shape, init=init)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.w_en & self.port.w_stb):
            m.d.sync += self._storage.eq(self.port.w_data)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class RxPeripheral(wiring.Component):
    class Config(csr.Register, access="rw"):
        """Peripheral configuration register.

        This :class:`Register` has the following fields:

        .. bitfield::
            :bits: 8

                [
                    { "name": "enable", "bits": 1, "attr": "RW" },
                    { "bits": 7, "attr": "ResR0W0" },
                ]

        - If the ``enable`` field is 0, the PHY is held in reset state.
        - If the ``enable`` field is 1, the PHY operates normally.
        """
        enable: csr.Field(csr.action.RW,      1)
        _unimp: csr.Field(csr.action.ResR0W0, 7)

    class PhyConfig(csr.Register, access="rw"):
        """PHY configuration register.

        This :class:`Register` is writable if the ``enable`` field of :class:`RxPeripheral.Config`
        is 0, and read-only otherwise. It has a single field with an implementation-specific shape
        given by the ``phy_config_shape`` parameter.

        If ``phy_config_shape`` is ``unsigned(16)``, then the register has the following field:

        .. bitfield::
            :bits: 16

                [
                    { "name": "phy_config", "bits": 16, "attr": "RW" },
                ]

        Parameters
        ----------
        phy_config_shape : :ref:`shape-like <lang-shapelike>`
            Shape of the PHY configuration word.
        phy_config_init : :class:`int`
            Initial value of the PHY configuration word.
        """
        def __init__(self, phy_config_shape, phy_config_init):
            super().__init__(csr.Field(_PhyConfigFieldAction, phy_config_shape,
                                       init=phy_config_init))

    class Status(csr.Register, access="rw"):
        """Status register.

        This :class:`Register` is read to be informed of available data or error conditions.

        It has the following fields:

        .. bitfield::
            :bits: 8

                [
                    { "name": "ready",    "bits": 1, "attr": "R" },
                    { "name": "overflow", "bits": 1, "attr": "RW1C" },
                    { "name": "error",    "bits": 1, "attr": "RW1C" },
                    { "bits": 5, "attr": "ResR0W0" },
                ]

        - The ``ready`` field is set if the receiver buffer is non-empty.
        - The ``overflow`` field is set and latched if a symbol is received while the receiver
          buffer is full.
        - The ``error`` field is set and latched if any implementation-specific error occured.
        """
        ready:    csr.Field(csr.action.R,       1)
        overflow: csr.Field(csr.action.RW1C,    1)
        error:    csr.Field(csr.action.RW1C,    1)
        _unimp:   csr.Field(csr.action.ResR0W0, 5)

    class Data(csr.Register, access="r"):
        """Data register.

        This :class:`Register` is read to consume data from the receiver buffer. It has a single
        field with an implementation-specific shape given by the ``symbol_shape`` parameter.

        If ``symbol_shape`` is ``unsigned(8)``, then the register has the following field:

        .. bitfield::
            :bits: 8

                [
                    { "name": "data", "bits": 8, "attr": "R" },
                ]

        - If either the ``enable`` field of :class:`RxPeripheral.Config` or the ``ready`` field of
          :class:`RxPeripheral.Status` are 0, reading from this register has no side-effect and
          returns an unspecified value.
        - If both the ``enable`` field of :class:`RxPeripheral.Config` and the ``ready`` field of
          :class:`RxPeripheral.Status` are 1, reading from this register consumes one symbol from
          the receiver buffer and returns it.

        Parameters
        ----------
        symbol_shape : :ref:`shape-like <lang-shapelike>`
            Shape of a symbol.
        """
        def __init__(self, symbol_shape):
            super().__init__(csr.Field(csr.action.R, symbol_shape))

    """UART receiver peripheral.

    Parameters
    ----------
    addr_width : :class:`int`
        CSR bus address width.
    data_width : :class:`int`
        CSR bus data width.
    phy_config_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the PHY configuration word. Optional. Defaults to ``unsigned(16)``.
    phy_config_init : :class:`int`
        Initial value of the PHY configuration word. Optional. Defaults to ``0``.
    symbol_shape : :ref:`shape-like <lang-shapelike>`
        Shape of a symbol. Optional. Defaults to ``unsigned(8)``.

    Members
    -------
    bus : :py:`In(csr.Signature(addr_width, data_width))`
        CSR bus interface providing access to registers.
    phy : :py:`Out(RxPhySignature(phy_config_shape, symbol_shape))`
        Interface between the peripheral and its PHY.
    """
    def __init__(self, *, addr_width, data_width, phy_config_shape=unsigned(16),
                 phy_config_init=0, symbol_shape=unsigned(8)):
        regs = csr.Builder(addr_width=addr_width, data_width=data_width)

        self._config     = regs.add("Config",    self.Config())
        self._phy_config = regs.add("PhyConfig", self.PhyConfig(phy_config_shape, phy_config_init))
        self._status     = regs.add("Status",    self.Status())
        self._data       = regs.add("Data",      self.Data(symbol_shape))

        self._bridge = csr.Bridge(regs.as_memory_map())

        super().__init__({
            "bus": In(csr.Signature(addr_width=addr_width, data_width=data_width)),
            "phy": Out(RxPhySignature(phy_config_shape, symbol_shape)),
        })
        self.bus.memory_map = self._bridge.bus.memory_map

        self._phy_config_shape = phy_config_shape
        self._phy_config_init  = phy_config_init
        self._symbol_shape     = symbol_shape

    @property
    def phy_config_shape(self):
        """Shape of the PHY configuration word.

        Returns
        -------
        :ref:`shape-like <lang-shapelike>`
        """
        return self._phy_config_shape

    @property
    def phy_config_init(self):
        """Initial value of the PHY configuration word.

        Returns
        -------
        :class:`int`
        """
        return self._phy_config_init

    @property
    def symbol_shape(self):
        """Shape of a symbol.

        Returns
        -------
        :ref:`shape-like <lang-shapelike>`
        """
        return self._symbol_shape

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge = self._bridge

        connect(m, flipped(self.bus), self._bridge.bus)

        m.d.comb += [
            self.phy.rst.eq(~self._config.f.enable.data),

            self._phy_config.f.w_en.eq(self.phy.rst),
            self.phy.config.eq(self._phy_config.f.data),

            self._status.f.ready.r_data.eq(self.phy.symbols.valid),
            self._data.f.r_data.eq(self.phy.symbols.payload),
            self.phy.symbols.ready.eq(self._data.f.r_stb),

            self._status.f.overflow.set.eq(self.phy.overflow),
            self._status.f.error.set.eq(self.phy.error),
        ]

        return m


class TxPeripheral(wiring.Component):
    class Config(csr.Register, access="rw"):
        """Peripheral configuration register.

        This :class:`Register` has the following fields:

        .. bitfield::
            :bits: 8

                [
                    { "name": "enable", "bits": 1, "attr": "RW" },
                    { "bits": 7, "attr": "ResR0W0" },
                ]

        - If the ``enable`` bit is 0, the PHY is held in reset state.
        - If the ``enable`` bit is 1, the PHY operates normally.
        """
        enable: csr.Field(csr.action.RW,      1)
        _unimp: csr.Field(csr.action.ResR0W0, 7)

    class PhyConfig(csr.Register, access="rw"):
        """PHY configuration register.

        This :class:`Register` is writable if the ``enable`` field of :class:`TxPeripheral.Config`
        is 0, and read-only otherwise. It has a single field with an implementation-specific shape
        given by the ``phy_config_shape`` parameter.

        If ``phy_config_shape`` is ``unsigned(16)``, then the register has the following field:

        .. bitfield::
            :bits: 16

                [
                    { "name": "phy_config", "bits": 16, "attr": "RW" },
                ]

        Parameters
        ----------
        phy_config_shape : :ref:`shape-like <lang-shapelike>`
            Shape of the PHY configuration word.
        phy_config_init : :class:`int`
            Initial value of the PHY configuration word.
        """
        def __init__(self, phy_config_shape, phy_config_init):
            super().__init__(csr.Field(_PhyConfigFieldAction, phy_config_shape,
                                       init=phy_config_init))

    class Status(csr.Register, access="r"):
        """Status register.

        This :class:`Register` is read to be informed of when the transmitter can accept data.

        It has the following fields:

        .. bitfield::
            :bits: 8

                [
                    { "name": "ready", "bits": 1, "attr": "R" },
                    { "bits": 7, "attr": "ResR0W0" },
                ]

        - The ``ready`` field is set if the transmitter buffer is non-full.
        """
        ready:  csr.Field(csr.action.R,       1)
        _unimp: csr.Field(csr.action.ResR0W0, 7)

    class Data(csr.Register, access="w"):
        """Data register.

        This :class:`Register` is written to append data to the transmitter buffer. It has a single
        field with an implementation-specific shape given by the ``symbol_shape`` parameter.

        If ``symbol_shape`` is ``unsigned(8)``, then the register has the following field:

        .. bitfield::
            :bits: 8

                [
                    { "name": "data", "bits": 8, "attr": "W" },
                ]

        - If either the ``enable`` field of :class:`TxPeripheral.Config` or the ``ready`` field of
          :class:`TxPeripheral.Status` are 0, writing to this register has no side-effect.
        - If both the ``enable`` field of :class:`TxPeripheral.Config` and the ``ready`` field of
          :class:`TxPeripheral.Status` are 1, writing to this register appends one symbol to the
          transmitter buffer.

        Parameters
        ----------
        symbol_shape : :ref:`shape-like <lang-shapelike>`
            Shape of a symbol.
        """
        def __init__(self, symbol_shape):
            super().__init__(csr.Field(csr.action.W, symbol_shape))

    """UART transmitter peripheral.

    Parameters
    ----------
    addr_width : :class:`int`
        CSR bus address width.
    data_width : :class:`int`
        CSR bus data width.
    phy_config_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the PHY configuration word. Optional. Defaults to ``unsigned(16)``.
    phy_config_init : :class:`int`
        Initial value of the PHY configuration word. Optional. Defaults to ``0``.
    symbol_shape : :ref:`shape-like <lang-shapelike>`
        Shape of a symbol. Optional. Defaults to ``unsigned(8)``.

    Members
    -------
    bus : :py:`In(csr.Signature(addr_width, data_width))`
        CSR bus interface providing access to registers.
    phy : :py:`Out(TxPhySignature(phy_config_shape, symbol_shape))`
        Interface between the peripheral and its PHY.
    """
    def __init__(self, *, addr_width, data_width=8, phy_config_shape=unsigned(16),
                 phy_config_init=0, symbol_shape=unsigned(8)):
        regs = csr.Builder(addr_width=addr_width, data_width=data_width)

        self._config     = regs.add("Config",    self.Config())
        self._phy_config = regs.add("PhyConfig", self.PhyConfig(phy_config_shape, phy_config_init))
        self._status     = regs.add("Status",    self.Status())
        self._data       = regs.add("Data",      self.Data(symbol_shape))

        self._bridge = csr.Bridge(regs.as_memory_map())

        super().__init__({
            "bus": In(csr.Signature(addr_width=addr_width, data_width=data_width)),
            "phy": Out(TxPhySignature(phy_config_shape, symbol_shape)),
        })
        self.bus.memory_map = self._bridge.bus.memory_map

        self._phy_config_shape = phy_config_shape
        self._phy_config_init  = phy_config_init
        self._symbol_shape     = symbol_shape

    @property
    def phy_config_shape(self):
        """Shape of the PHY configuration word.

        Returns
        -------
        :ref:`shape-like <lang-shapelike>`
        """
        return self._phy_config_shape

    @property
    def phy_config_init(self):
        """Initial value of the PHY configuration word.

        Returns
        -------
        :class:`int`
        """
        return self._phy_config_init

    @property
    def symbol_shape(self):
        """Shape of a symbol.

        Returns
        -------
        :ref:`shape-like <lang-shapelike>`
        """
        return self._symbol_shape

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge = self._bridge

        connect(m, flipped(self.bus), self._bridge.bus)

        m.d.comb += [
            self.phy.rst.eq(~self._config.f.enable.data),

            self._phy_config.f.w_en.eq(self.phy.rst),
            self.phy.config.eq(self._phy_config.f.data),

            self._status.f.ready.r_data.eq(self.phy.symbols.ready),
            self.phy.symbols.payload.eq(self._data.f.w_data),
            self.phy.symbols.valid.eq(self._data.f.w_stb),
        ]

        return m


class Peripheral(wiring.Component):
    """UART transceiver peripheral.

    This peripheral is composed of two subordinate peripherals. A :class:`RxPeripheral` occupies
    the bottom half of the address space, and a :class:`TxPeripheral` occupies the top half.
    Both subordinates have the same parameters as this peripheral, except ``addr_width`` (which
    becomes ``addr_width - 1``).

    Parameters
    ----------
    addr_width : :class:`int`
        CSR bus address width.
    data_width : :class:`int`
        CSR bus data width.
    phy_config_shape : :ref:`shape-like <lang-shapelike>`
        Shape of the PHY configuration word. Optional. Defaults to ``unsigned(16)``.
    phy_config_init : :class:`int`
        Initial value of the PHY configuration word. Optional. Defaults to ``0``.
    symbol_shape : :ref:`shape-like <lang-shapelike>`
        Shape of a symbol. Optional. Defaults to ``unsigned(8)``.

    Members
    -------
    bus : :py:`In(csr.Signature(addr_width, data_width))`
        CSR bus interface providing access to registers.
    rx : :py:`Out(RxPhySignature(phy_config_shape, symbol_shape))`
        Interface between the peripheral and its PHY receiver.
    tx : :py:`Out(TxPhySignature(phy_config_shape, symbol_shape))`
        Interface between the peripheral and its PHY transmitter.

    Raises
    ------
    :exc:`TypeError`
        If ``addr_width`` is not a positive integer.
    """
    def __init__(self, *, addr_width, data_width=8, phy_config_shape=unsigned(16),
                 phy_config_init=0, symbol_shape=unsigned(8)):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise TypeError(f"Address width must be a positive integer, not {addr_width!r}")

        self._rx = RxPeripheral(addr_width=addr_width - 1, data_width=data_width,
                                phy_config_shape=phy_config_shape, phy_config_init=phy_config_init,
                                symbol_shape=symbol_shape)
        self._tx = TxPeripheral(addr_width=addr_width - 1, data_width=data_width,
                                phy_config_shape=phy_config_shape, phy_config_init=phy_config_init,
                                symbol_shape=symbol_shape)

        self._decoder = csr.Decoder(addr_width=addr_width, data_width=data_width)
        self._decoder.add(self._rx.bus, name="rx")
        self._decoder.add(self._tx.bus, name="tx")

        super().__init__({
            "bus": In(csr.Signature(addr_width=addr_width, data_width=data_width)),
            "rx":  Out(RxPhySignature(phy_config_shape, symbol_shape)),
            "tx":  Out(TxPhySignature(phy_config_shape, symbol_shape)),
        })
        self.bus.memory_map = self._decoder.bus.memory_map

        self._phy_config_shape = phy_config_shape
        self._phy_config_init  = phy_config_init
        self._symbol_shape     = symbol_shape

    @property
    def phy_config_shape(self):
        """Shape of the PHY configuration word.

        Returns
        -------
        :ref:`shape-like <lang-shapelike>`
        """
        return self._phy_config_shape

    @property
    def phy_config_init(self):
        """Initial value of the PHY configuration word.

        Returns
        -------
        :class:`int`
        """
        return self._phy_config_init

    @property
    def symbol_shape(self):
        """Shape of a symbol.

        Returns
        -------
        :ref:`shape-like <lang-shapelike>`
        """
        return self._symbol_shape

    def elaborate(self, platform):
        m = Module()
        m.submodules.decoder = self._decoder
        m.submodules.rx = self._rx
        m.submodules.tx = self._tx

        connect(m, flipped(self.bus), self._decoder.bus)
        connect(m, self._rx.phy, flipped(self.rx))
        connect(m, self._tx.phy, flipped(self.tx))

        return m
