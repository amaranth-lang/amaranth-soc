import unittest

from ..memory import _RangeMap, MemoryMap


class RangeMapTestCase(unittest.TestCase):
    def test_insert(self):
        range_map = _RangeMap()
        range_map.insert(range(0,10), "a")
        range_map.insert(range(20,21), "c")
        range_map.insert(range(15,16), "b")
        range_map.insert(range(16,20), "q")
        self.assertEqual(range_map._keys, [
            range(0,10), range(15,16), range(16,20), range(20,21)
        ])

    def test_overlaps(self):
        range_map = _RangeMap()
        range_map.insert(range(10,20), "a")
        self.assertEqual(range_map.overlaps(range(5,15)), ["a"])
        self.assertEqual(range_map.overlaps(range(15,25)), ["a"])
        self.assertEqual(range_map.overlaps(range(5,25)), ["a"])
        self.assertEqual(range_map.overlaps(range(0,3)), [])
        self.assertEqual(range_map.overlaps(range(0,5)), [])
        self.assertEqual(range_map.overlaps(range(25,30)), [])

    def test_insert_wrong_overlap(self):
        range_map = _RangeMap()
        range_map.insert(range(0,10), "a")
        with self.assertRaises(AssertionError):
            range_map.insert(range(5,15), "b")

    def test_get(self):
        range_map = _RangeMap()
        range_map.insert(range(5,15), "a")
        self.assertEqual(range_map.get(0), None)
        self.assertEqual(range_map.get(5), "a")
        self.assertEqual(range_map.get(10), "a")
        self.assertEqual(range_map.get(14), "a")
        self.assertEqual(range_map.get(15), None)


class MemoryMapTestCase(unittest.TestCase):
    def test_wrong_addr_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width must be a positive integer, not -1"):
            MemoryMap(addr_width=-1, data_width=8)

    def test_wrong_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive integer, not -1"):
            MemoryMap(addr_width=16, data_width=-1)

    def test_wrong_alignment(self):
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not -1"):
            MemoryMap(addr_width=16, data_width=8, alignment=-1)

    def test_set_addr_width_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width must be a positive integer, not -1"):
            memory_map = MemoryMap(addr_width=1, data_width=8)
            memory_map.addr_width = -1

    def test_set_addr_width_wrong_shrink(self):
        with self.assertRaisesRegex(ValueError,
                r"Address width 1 must not be less than its previous value 2, "
                r"because resources that were previously added may not fit anymore"):
            memory_map = MemoryMap(addr_width=2, data_width=8)
            memory_map.addr_width = 1

    def test_set_addr_width_wrong_frozen(self):
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen. Address width cannot be extended "
                r"further"):
            memory_map = MemoryMap(addr_width=1, data_width=8)
            memory_map.freeze()
            memory_map.addr_width = 2

    def test_add_resource(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=1), (0, 1))
        self.assertEqual(memory_map.add_resource(resource="b", size=2), (1, 3))

    def test_add_resource_map_aligned(self):
        memory_map = MemoryMap(addr_width=16, data_width=8, alignment=1)
        self.assertEqual(memory_map.add_resource("a", size=1), (0, 2))
        self.assertEqual(memory_map.add_resource("b", size=2), (2, 4))

    def test_add_resource_explicit_aligned(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=1), (0, 1))
        self.assertEqual(memory_map.add_resource("b", size=1, alignment=1), (2, 4))
        self.assertEqual(memory_map.add_resource("c", size=2), (4, 6))

    def test_add_resource_addr(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=1, addr=10), (10, 11))
        self.assertEqual(memory_map.add_resource("b", size=2), (11, 13))

    def test_add_resource_extend(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=1, addr=0x10000, extend=True),
                         (0x10000, 0x10001))
        self.assertEqual(memory_map.addr_width, 17)

    def test_add_resource_size_zero(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=0), (0, 1))
        self.assertEqual(memory_map.add_resource("b", size=0), (1, 2))

    def test_add_resource_wrong_address(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Address must be a non-negative integer, not -1"):
            memory_map.add_resource("a", size=1, addr=-1)

    def test_add_resource_wrong_address_unaligned(self):
        memory_map = MemoryMap(addr_width=16, data_width=8, alignment=1)
        with self.assertRaisesRegex(ValueError,
                r"Explicitly specified address 0x1 must be a multiple of 0x2 bytes"):
            memory_map.add_resource("a", size=1, addr=1)

    def test_add_resource_wrong_size(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Size must be a non-negative integer, not -1"):
            memory_map.add_resource("a", size=-1)

    def test_add_resource_wrong_alignment(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not -1"):
            memory_map.add_resource("a", size=1, alignment=-1)

    def test_add_resource_wrong_out_of_bounds(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x10000\.\.0x10001 out of bounds for memory map spanning "
                r"range 0x0\.\.0x10000 \(16 address bits\)"):
            memory_map.add_resource("a", addr=0x10000, size=1)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x0\.\.0x10001 out of bounds for memory map spanning "
                r"range 0x0\.\.0x10000 \(16 address bits\)"):
            memory_map.add_resource("a", size=0x10001)

    def test_add_resource_wrong_overlap(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_resource("a", size=16)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0xa\.\.0xb overlaps with resource 'a' at 0x0\.\.0x10"):
            memory_map.add_resource("b", size=1, addr=10)

    def test_add_resource_wrong_twice(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_resource("a", size=16)
        with self.assertRaisesRegex(ValueError,
                r"Resource 'a' is already added at address range 0x0..0x10"):
            memory_map.add_resource("a", size=16)

    def test_iter_resources(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_resource("a", size=1)
        memory_map.add_resource("b", size=2)
        self.assertEqual(list(memory_map.resources()), [
            ("a", (0, 1)),
            ("b", (1, 3)),
        ])

    def test_add_window(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=1), (0, 1))
        self.assertEqual(memory_map.add_window(MemoryMap(addr_width=10, data_width=8)),
                         (0x400, 0x800, 1))
        self.assertEqual(memory_map.add_resource("b", size=1), (0x800, 0x801))

    def test_add_window_sparse(self):
        memory_map = MemoryMap(addr_width=16, data_width=32)
        self.assertEqual(memory_map.add_window(MemoryMap(addr_width=10, data_width=8),
                                               sparse=True),
                         (0, 0x400, 1))

    def test_add_window_dense(self):
        memory_map = MemoryMap(addr_width=16, data_width=32)
        self.assertEqual(memory_map.add_window(MemoryMap(addr_width=10, data_width=8),
                                               sparse=False),
                         (0, 0x100, 4))

    def test_add_window_extend(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_window(MemoryMap(addr_width=17, data_width=8),
                                               extend=True),
                         (0, 0x20000, 1))
        self.assertEqual(memory_map.addr_width, 18)

    def test_add_window_wrong_window(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Window must be a MemoryMap, not 'a'"):
            memory_map.add_window(window="a")

    def test_add_window_wrong_wider(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Window has data width 16, and cannot be added to a memory map "
                r"with data width 8"):
            memory_map.add_window(MemoryMap(addr_width=10, data_width=16))

    def test_add_window_wrong_no_mode(self):
        memory_map = MemoryMap(addr_width=16, data_width=16)
        with self.assertRaisesRegex(ValueError,
                r"Address translation mode must be explicitly specified when adding "
                r"a window with data width 8 to a memory map with data width 16"):
            memory_map.add_window(MemoryMap(addr_width=10, data_width=8))

    def test_add_window_wrong_ratio(self):
        memory_map = MemoryMap(addr_width=16, data_width=16)
        with self.assertRaisesRegex(ValueError,
                r"Dense addressing cannot be used because the memory map data width "
                r"16 is not an integer multiple of window data width 7"):
            memory_map.add_window(MemoryMap(addr_width=10, data_width=7), sparse=False)

    def test_add_window_wrong_out_of_bounds(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x0\.\.0x20000 out of bounds for memory map spanning "
                r"range 0x0\.\.0x10000 \(16 address bits\)"):
            memory_map.add_window(MemoryMap(addr_width=17, data_width=8))

    def test_add_window_wrong_overlap(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_window(MemoryMap(addr_width=10, data_width=8))
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x200\.\.0x600 overlaps with window "
                r"<nmigen_soc\.memory\.MemoryMap object at .+?> at 0x0\.\.0x400"):
            memory_map.add_window(MemoryMap(addr_width=10, data_width=8), addr=0x200)

    def test_add_window_wrong_twice(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        window = MemoryMap(addr_width=10, data_width=8)
        memory_map.add_window(window)
        with self.assertRaisesRegex(ValueError,
                r"Window <nmigen_soc\.memory\.MemoryMap object at .+?> is already added "
                r"at address range 0x0\.\.0x400"):
            memory_map.add_window(window)

    def test_iter_windows(self):
        memory_map = MemoryMap(addr_width=16, data_width=16)
        window_1 = MemoryMap(addr_width=10, data_width=8)
        memory_map.add_window(window_1, sparse=False)
        window_2 = MemoryMap(addr_width=12, data_width=16)
        memory_map.add_window(window_2)
        self.assertEqual(list(memory_map.windows()), [
            (window_1, (0, 0x200, 2)),
            (window_2, (0x1000, 0x2000, 1)),
        ])

    def test_iter_window_patterns(self):
        memory_map = MemoryMap(addr_width=16, data_width=16)
        window_1 = MemoryMap(addr_width=10, data_width=8)
        memory_map.add_window(window_1, sparse=False)
        window_2 = MemoryMap(addr_width=12, data_width=16)
        memory_map.add_window(window_2)
        self.assertEqual(list(memory_map.window_patterns()), [
            (window_1, ("000000----------", 2)),
            (window_2, ("0001------------", 1)),
        ])

    def test_iter_window_patterns_covered(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        window = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_window(window)
        self.assertEqual(list(memory_map.window_patterns()), [
            (window, ("----------------", 1)),
        ])

    def test_align_to(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", size=1), (0, 1))
        self.assertEqual(memory_map.align_to(10), 0x400)
        self.assertEqual(memory_map.add_resource("b", size=16), (0x400, 0x410))

    def test_align_to_wrong(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not -1"):
            memory_map.align_to(alignment=-1)


class MemoryMapDiscoveryTestCase(unittest.TestCase):
    def setUp(self):
        self.root = MemoryMap(addr_width=32, data_width=32)
        self.res1 = "res1"
        self.root.add_resource(self.res1, size=16)
        self.win1 = MemoryMap(addr_width=16, data_width=32)
        self.root.add_window(self.win1)
        self.res2 = "res2"
        self.win1.add_resource(self.res2, size=32)
        self.res3 = "res3"
        self.win1.add_resource(self.res3, size=32)
        self.res4 = "res4"
        self.root.add_resource(self.res4, size=1)
        self.win2 = MemoryMap(addr_width=16, data_width=8)
        self.root.add_window(self.win2, sparse=True)
        self.res5 = "res5"
        self.win2.add_resource(self.res5, size=16)
        self.win3 = MemoryMap(addr_width=16, data_width=8)
        self.root.add_window(self.win3, sparse=False)
        self.res6 = "res6"
        self.win3.add_resource(self.res6, size=16)

    def test_iter_all_resources(self):
        self.assertEqual(list(self.root.all_resources()), [
            (self.res1, (0x00000000, 0x00000010, 32)),
            (self.res2, (0x00010000, 0x00010020, 32)),
            (self.res3, (0x00010020, 0x00010040, 32)),
            (self.res4, (0x00020000, 0x00020001, 32)),
            (self.res5, (0x00030000, 0x00030010, 8)),
            (self.res6, (0x00040000, 0x00040004, 32)),
        ])

    def test_find_resource(self):
        for res, loc in self.root.all_resources():
            self.assertEqual(self.root.find_resource(res), loc)

    def test_find_resource_wrong(self):
        with self.assertRaises(KeyError) as error:
            self.root.find_resource("resNA")
        self.assertEqual(error.exception.args, ("resNA",))

    def test_decode_address(self):
        for res, (start, end, width) in self.root.all_resources():
            self.assertEqual(self.root.decode_address(start), res)
            self.assertEqual(self.root.decode_address(end - 1), res)

    def test_decode_address_missing(self):
        self.assertIsNone(self.root.decode_address(address=0x00000100))
