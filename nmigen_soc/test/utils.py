from nmigen import *
from .. import csr

class MockRegister(Elaboratable):
    def __init__(self, name, width):
        self.element = csr.Element(width, "rw", name=name)
        self.r_count = Signal(8)
        self.w_count = Signal(8)
        self.data    = Signal(width)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.element.r_stb):
            m.d.sync += self.r_count.eq(self.r_count + 1)
        m.d.comb += self.element.r_data.eq(self.data)

        with m.If(self.element.w_stb):
            m.d.sync += self.w_count.eq(self.w_count + 1)
            m.d.sync += self.data.eq(self.element.w_data)

        return m
