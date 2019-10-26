import unittest
from nmigen import *
from nmigen.hdl.rec import *

from ..wishbone.bus import *


class InterfaceTestCase(unittest.TestCase):
    def test_simple(self):
        iface = Interface(addr_width=32, data_width=8)
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 8)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.memory_map.addr_width, 32)
        self.assertEqual(iface.memory_map.data_width, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   32, DIR_FANOUT),
            ("dat_w", 8,  DIR_FANOUT),
            ("dat_r", 8,  DIR_FANIN),
            ("sel",   1,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
        ]))

    def test_granularity(self):
        iface = Interface(addr_width=30, data_width=32, granularity=8)
        self.assertEqual(iface.addr_width, 30)
        self.assertEqual(iface.data_width, 32)
        self.assertEqual(iface.granularity, 8)
        self.assertEqual(iface.memory_map.addr_width, 32)
        self.assertEqual(iface.memory_map.data_width, 8)
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   30, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",   4,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
        ]))

    def test_optional(self):
        iface = Interface(addr_width=32, data_width=32,
                          optional={"rty", "err", "stall", "lock", "cti", "bte"})
        self.assertEqual(iface.layout, Layout.cast([
            ("adr",   32, DIR_FANOUT),
            ("dat_w", 32, DIR_FANOUT),
            ("dat_r", 32, DIR_FANIN),
            ("sel",   1,  DIR_FANOUT),
            ("cyc",   1,  DIR_FANOUT),
            ("stb",   1,  DIR_FANOUT),
            ("we",    1,  DIR_FANOUT),
            ("ack",   1,  DIR_FANIN),
            ("err",   1,  DIR_FANIN),
            ("rty",   1,  DIR_FANIN),
            ("stall", 1,  DIR_FANIN),
            ("lock",  1,  DIR_FANOUT),
            ("cti",   CycleType,    DIR_FANOUT),
            ("bte",   BurstTypeExt, DIR_FANOUT),
        ]))

    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width must be a non-negative integer, not -1"):
            Interface(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be one of 8, 16, 32, 64, not 7"):
            Interface(addr_width=0, data_width=7)

    def test_wrong_granularity(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity must be one of 8, 16, 32, 64, not 7"):
            Interface(addr_width=0, data_width=32, granularity=7)

    def test_wrong_granularity_wide(self):
        with self.assertRaisesRegex(ValueError,
                r"Granularity 32 may not be greater than data width 8"):
            Interface(addr_width=0, data_width=8, granularity=32)

    def test_wrong_optional(self):
        with self.assertRaisesRegex(ValueError,
                r"Optional signal\(s\) 'foo' are not supported"):
            Interface(addr_width=0, data_width=8, optional={"foo"})
