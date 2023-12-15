from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from .reg import FieldPort


__all__ = ["R", "W", "RW", "RW1C", "RW1S"]


class R(wiring.Component):
    """A read-only field.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.

    Interface attributes
    --------------------
    port : :class:`FieldPort`
        Field port.
    r_data : Signal(shape)
        Read data. Drives the :attr:`~FieldPort.r_data` signal of ``port``.
    """
    def __init__(self, shape):
        super().__init__({
            "port":   In(FieldPort.Signature(shape, access="r")),
            "r_data": In(shape),
        })

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.port.r_data.eq(self.r_data)
        return m


class W(wiring.Component):
    """A write-only field.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.

    Interface attributes
    --------------------
    port : :class:`FieldPort`
        Field port.
    w_data : Signal(shape)
        Write data. Driven by the :attr:`~FieldPort.w_data` signal of ``port``.
    """
    def __init__(self, shape):
        super().__init__({
            "port":   In(FieldPort.Signature(shape, access="w")),
            "w_data": Out(shape),
        })

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.w_data.eq(self.port.w_data)
        return m


class RW(wiring.Component):
    """A read/write field with built-in storage.

    Storage is updated with the value of ``port.w_data`` one clock cycle after ``port.w_stb`` is
    asserted.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    reset : :class:`int`
        Storage reset value.

    Interface attributes
    --------------------
    port : :class:`FieldPort`
        Field port.
    data : Signal(shape)
        Storage output.
    """
    def __init__(self, shape, *, reset=0):
        super().__init__({
            "port": In(FieldPort.Signature(shape, access="rw")),
            "data": Out(shape),
        })
        self._storage = Signal(shape, reset=reset)
        self._reset   = reset

    @property
    def reset(self):
        return self._reset

    def elaborate(self, platform):
        m = Module()

        with m.If(self.port.w_stb):
            m.d.sync += self._storage.eq(self.port.w_data)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class RW1C(wiring.Component):
    """A read/write-one-to-clear field with built-in storage.

    Storage bits are:
      * cleared by high bits in ``port.w_data``, one clock cycle after ``port.w_stb`` is asserted;
      * set by high bits in ``set``, one clock cycle after they are asserted.

    If a storage bit is set and cleared on the same clock cycle, setting it has precedence.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    reset : :class:`int`
        Storage reset value.

    Interface attributes
    --------------------
    port : :class:`FieldPort`
        Field port.
    data : Signal(shape)
        Storage output.
    set : Signal(shape)
        Mask to set storage bits.
    """
    def __init__(self, shape, *, reset=0):
        super().__init__({
            "port": In(FieldPort.Signature(shape, access="rw")),
            "data": Out(shape),
            "set":  In(shape),
        })
        self._storage = Signal(shape, reset=reset)
        self._reset   = reset

    @property
    def reset(self):
        return self._reset

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


class RW1S(wiring.Component):
    """A read/write-one-to-set field with built-in storage.

    Storage bits are:
      * set by high bits in ``port.w_data``, one clock cycle after ``port.w_stb`` is asserted;
      * cleared by high bits in ``clear``, one clock cycle after they are asserted.

    If a storage bit is set and cleared on the same clock cycle, setting it has precedence.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    reset : :class:`int`
        Storage reset value.

    Interface attributes
    --------------------
    port : :class:`FieldPort`
        Field port.
    data : Signal(shape)
        Storage output.
    clear : Signal(shape)
        Mask to clear storage bits.
    """
    def __init__(self, shape, *, reset=0):
        super().__init__({
            "port":  In(FieldPort.Signature(shape, access="rw")),
            "clear": In(shape),
            "data":  Out(shape),
        })
        self._storage = Signal(shape, reset=reset)
        self._reset   = reset

    @property
    def reset(self):
        return self._reset

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
