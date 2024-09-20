# nmigen: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.hdl.rec import Layout

from .. import sram
from ..memory import MemoryMap


class InterfaceTestCase(unittest.TestCase):
    def test_layout(self):
        iface = sram.Interface(addr_width=12, data_width=8)
        self.assertEqual(iface.addr_width, 12)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("a", 12),
            ("d_r", 8),
            ("d_w", 8),
            ("we", 1),
            ("ce", 1),
        ]))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(
                ValueError,
                r"Address width must be a positive integer, not -1",
        ):
            sram.Interface(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(
            ValueError,
            r"Data width must be a positive integer, not -1",
        ):
            sram.Interface(addr_width=16, data_width=-1)

    def test_no_set_map(self):
        iface = sram.Interface(addr_width=16, data_width=8)
        with self.assertRaisesRegex(AttributeError, "can't set attribute"):
            iface.memory_map = MemoryMap(addr_width=16, data_width=8)
