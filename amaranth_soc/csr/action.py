from amaranth import *
from amaranth.lib.wiring import In, Out

from .reg import FieldAction


__all__ = ["R", "W", "RW", "RW1C", "RW1S", "ResRAW0", "ResRAWL", "ResR0WA", "ResR0W0"]


class R(FieldAction):
    """A read-only :class:`~.csr.reg.FieldAction`.

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, "r"))`
        Field port.
    r_data : :py:`In(shape)`
        Read data. Drives ``port.r_data``.
    r_stb : :py:`Out(1)`
        Read strobe. Driven by ``port.r_stb``.
    """
    def __init__(self, shape):
        super().__init__(shape, access="r", members={
            "r_data": In(shape),
            "r_stb":  Out(1)
        })

    def elaborate(self, platform):
        m = Module()
        m.d.comb += [
            self.port.r_data.eq(self.r_data),
            self.r_stb.eq(self.port.r_stb),
        ]
        return m


class W(FieldAction):
    """A write-only :class:`~.csr.reg.FieldAction`.

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, "w"))`
        Field port.
    w_data : :py:`Out(shape)`
        Write data. Driven by ``port.w_data``.
    w_stb : :py:`Out(1)`
        Write strobe. Driven by ``port.w_stb``.
    """
    def __init__(self, shape):
        super().__init__(shape, access="w", members={
            "w_data": Out(shape),
            "w_stb":  Out(1),
        })

    def elaborate(self, platform):
        m = Module()
        m.d.comb += [
            self.w_data.eq(self.port.w_data),
            self.w_stb.eq(self.port.w_stb),
        ]
        return m


class RW(FieldAction):
    """A read/write :class:`~.csr.reg.FieldAction`, with built-in storage.

    Storage is updated with the value of ``port.w_data`` one clock cycle after ``port.w_stb`` is
    asserted.

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.
    init : :class:`int`
        Storage initial value.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, "rw"))`
        Field port.
    data : :py:`Out(shape)`
        Storage output.
    """
    def __init__(self, shape, *, init=0):
        super().__init__(shape, access="rw", members={
            "data": Out(shape),
        })
        self._storage = Signal(shape, init=init)
        self._init    = init

    @property
    def init(self):
        """Storage initial value.

        Returns
        -------
        :class:`int`
        """
        return self._init

    def elaborate(self, platform):
        m = Module()

        with m.If(self.port.w_stb):
            m.d.sync += self._storage.eq(self.port.w_data)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class RW1C(FieldAction):
    """A read/write-one-to-clear :class:`~.csr.reg.FieldAction`, with built-in storage.

    Storage bits are:

      * cleared by high bits in ``port.w_data``, one clock cycle after ``port.w_stb`` is asserted;
      * set by high bits in ``set``, one clock cycle after they are asserted.

    If a storage bit is set and cleared on the same clock cycle, setting it has precedence.

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.
    init : :class:`int`
        Storage initial value.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, "rw"))`
        Field port.
    data : :py:`Out(shape)`
        Storage output.
    set : :py:`In(shape)`
        Mask to set storage bits.
    """
    def __init__(self, shape, *, init=0):
        super().__init__(shape, access="rw", members={
            "data": Out(shape),
            "set":  In(shape),
        })
        self._storage = Signal(shape, init=init)
        self._init    = init

    @property
    def init(self):
        """Storage initial value.

        Returns
        -------
        :class:`int`
        """
        return self._init

    def elaborate(self, platform):
        m = Module()

        for i, storage_bit in enumerate(self._storage):
            with m.If(self.port.w_stb & self.port.w_data[i]):
                m.d.sync += storage_bit.eq(0)
            with m.If(self.set[i]):
                m.d.sync += storage_bit.eq(1)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class RW1S(FieldAction):
    """A read/write-one-to-set :class:`~.csr.reg.FieldAction`, with built-in storage.

    Storage bits are:

      * set by high bits in ``port.w_data``, one clock cycle after ``port.w_stb`` is asserted;
      * cleared by high bits in ``clear``, one clock cycle after they are asserted.

    If a storage bit is set and cleared on the same clock cycle, setting it has precedence.

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.
    init : :class:`int`
        Storage initial value.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, "rw"))`
        Field port.
    data : :py:`Out(shape)`
        Storage output.
    clear : :py:`In(shape)`
        Mask to clear storage bits.
    """
    def __init__(self, shape, *, init=0):
        super().__init__(shape, access="rw", members={
            "data":  Out(shape),
            "clear": In(shape),
        })
        self._storage = Signal(shape, init=init)
        self._init    = init

    @property
    def init(self):
        """Storage initial value.

        Returns
        -------
        :class:`int`
        """
        return self._init

    def elaborate(self, platform):
        m = Module()

        for i, storage_bit in enumerate(self._storage):
            with m.If(self.clear[i]):
                m.d.sync += storage_bit.eq(0)
            with m.If(self.port.w_stb & self.port.w_data[i]):
                m.d.sync += storage_bit.eq(1)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class _Reserved(FieldAction):
    _doc_template = """
    {description}

    Arguments
    ---------
    shape : :ref:`shape-like object <lang-shapelike>`
        Shape of the field.

    Members
    -------
    port : :py:`In(csr.reg.FieldPort.Signature(shape, "nc"))`
        Field port.
    """
    def __init__(self, shape):
        super().__init__(shape, access="nc")

    def elaborate(self, platform):
        return Module()


class ResRAW0(_Reserved):
    __doc__ = _Reserved._doc_template.format(description="""
    A reserved read-any/write-zero :class:`~.csr.reg.FieldAction`.
    """)


class ResRAWL(_Reserved):
    __doc__ = _Reserved._doc_template.format(description="""
    A reserved read-any/write-last :class:`~.csr.reg.FieldAction`.
    """)


class ResR0WA(_Reserved):
    __doc__ = _Reserved._doc_template.format(description="""
    A reserved read-zero/write-any :class:`~.csr.reg.FieldAction`.
    """)


class ResR0W0(_Reserved):
    __doc__ = _Reserved._doc_template.format(description="""
    A reserved read-zero/write-zero :class:`~.csr.reg.FieldAction`.
    """)
