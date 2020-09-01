import unittest

from ..memory import _RangeMap, ResourceInfo, MemoryMap


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


class ResourceInfoTestCase(unittest.TestCase):
    def test_simple(self):
        info = ResourceInfo("a", name=("foo", "bar"), start=0, end=1, width=8)
        self.assertEqual(info.name, ("foo", "bar"))
        self.assertEqual(info.start, 0)
        self.assertEqual(info.end, 1)
        self.assertEqual(info.width, 8)

    def test_name_cast(self):
        info = ResourceInfo("a", name="foo", start=0, end=1, width=8)
        self.assertEqual(info.name, ("foo",))

    def test_wrong_name(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty sequence of non-empty strings, not \(1,\)"):
            ResourceInfo("a", name=(1,), start=0, end=1, width=8)
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty sequence of non-empty strings, not \(\)"):
            ResourceInfo("a", name=(), start=0, end=1, width=8)
        with self.assertRaisesRegex(TypeError,
                r"Name must be a non-empty sequence of non-empty strings, not \('foo', ''\)"):
            ResourceInfo("a", name=("foo", ""), start=0, end=1, width=8)

    def test_wrong_start_addr(self):
        with self.assertRaisesRegex(TypeError,
                r"Start address must be a non-negative integer, not 'foo'"):
            ResourceInfo("a", name="b", start="foo", end=1, width=8)
        with self.assertRaisesRegex(TypeError,
                r"Start address must be a non-negative integer, not -1"):
            ResourceInfo("a", name="b", start=-1, end=1, width=8)

    def test_wrong_end_addr(self):
        with self.assertRaisesRegex(TypeError,
                r"End address must be an integer greater than the start address, not 'foo'"):
            ResourceInfo("a", name="b", start=0, end="foo", width=8)
        with self.assertRaisesRegex(TypeError,
                r"End address must be an integer greater than the start address, not 0"):
            ResourceInfo("a", name="b", start=0, end=0, width=8)

    def test_wrong_width(self):
        with self.assertRaisesRegex(TypeError,
                r"Width must be a non-negative integer, not 'foo'"):
            ResourceInfo("a", name="b", start=0, end=1, width="foo")
        with self.assertRaisesRegex(TypeError,
                r"Width must be a non-negative integer, not -1"):
            ResourceInfo("a", name="b", start=0, end=1, width=-1)


class MemoryMapTestCase(unittest.TestCase):
    def test_name(self):
        memory_map_0 = MemoryMap(addr_width=1, data_width=8)
        memory_map_1 = MemoryMap(addr_width=1, data_width=8, name=None)
        memory_map_2 = MemoryMap(addr_width=1, data_width=8, name="foo")
        self.assertEqual(memory_map_0.name, None)
        self.assertEqual(memory_map_1.name, None)
        self.assertEqual(memory_map_2.name, "foo")

    def test_wrong_name(self):
        with self.assertRaisesRegex(ValueError,
                r"Name must be a non-empty string, not 1"):
            MemoryMap(addr_width=1, data_width=8, name=1)
        with self.assertRaisesRegex(ValueError,
                r"Name must be a non-empty string, not ''"):
            MemoryMap(addr_width=1, data_width=8, name="")

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
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1), (0, 1))
        self.assertEqual(memory_map.add_resource(resource="b", name="bar", size=2), (1, 3))

    def test_add_resource_map_aligned(self):
        memory_map = MemoryMap(addr_width=16, data_width=8, alignment=1)
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1), (0, 2))
        self.assertEqual(memory_map.add_resource("b", name="bar", size=2), (2, 4))

    def test_add_resource_explicit_aligned(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1), (0, 1))
        self.assertEqual(memory_map.add_resource("b", name="bar", size=1, alignment=1), (2, 4))
        self.assertEqual(memory_map.add_resource("c", name="baz", size=2), (4, 6))

    def test_add_resource_addr(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1, addr=10), (10, 11))
        self.assertEqual(memory_map.add_resource("b", name="bar", size=2), (11, 13))

    def test_add_resource_extend(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1, addr=0x10000,
                                                 extend=True),
                         (0x10000, 0x10001))
        self.assertEqual(memory_map.addr_width, 17)

    def test_add_resource_size_zero(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        self.assertEqual(memory_map.add_resource("a", name="foo", size=0), (0, 1))
        self.assertEqual(memory_map.add_resource("b", name="bar", size=0), (1, 2))

    def test_add_resource_wrong_frozen(self):
        memory_map = MemoryMap(addr_width=2, data_width=8)
        memory_map.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen. Cannot add resource 'a'"):
            memory_map.add_resource("a", name="foo", size=0)

    def test_add_resource_wrong_name(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        with self.assertRaisesRegex(TypeError, r"Name must be a non-empty string, not 1"):
            memory_map.add_resource("a", name=1, size=0)
        with self.assertRaisesRegex(TypeError, r"Name must be a non-empty string, not ''"):
            memory_map.add_resource("a", name="", size=0)

    def test_add_resource_wrong_name_conflict(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        memory_map.add_resource("a", name="foo", size=0)
        with self.assertRaisesRegex(ValueError, r"Name foo is already used by 'a'"):
            memory_map.add_resource("b", name="foo", size=0)

    def test_add_resource_wrong_address(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Address must be a non-negative integer, not -1"):
            memory_map.add_resource("a", name="foo", size=1, addr=-1)

    def test_add_resource_wrong_address_unaligned(self):
        memory_map = MemoryMap(addr_width=16, data_width=8, alignment=1)
        with self.assertRaisesRegex(ValueError,
                r"Explicitly specified address 0x1 must be a multiple of 0x2 bytes"):
            memory_map.add_resource("a", name="foo", size=1, addr=1)

    def test_add_resource_wrong_size(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Size must be a non-negative integer, not -1"):
            memory_map.add_resource("a", name="foo", size=-1)

    def test_add_resource_wrong_alignment(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not -1"):
            memory_map.add_resource("a", name="foo", size=1, alignment=-1)

    def test_add_resource_wrong_out_of_bounds(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x10000\.\.0x10001 out of bounds for memory map spanning "
                r"range 0x0\.\.0x10000 \(16 address bits\)"):
            memory_map.add_resource("a", name="foo", addr=0x10000, size=1)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0x0\.\.0x10001 out of bounds for memory map spanning "
                r"range 0x0\.\.0x10000 \(16 address bits\)"):
            memory_map.add_resource("a", name="foo", size=0x10001)

    def test_add_resource_wrong_overlap(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_resource("a", name="foo", size=16)
        with self.assertRaisesRegex(ValueError,
                r"Address range 0xa\.\.0xb overlaps with resource 'a' at 0x0\.\.0x10"):
            memory_map.add_resource("b", name="bar", size=1, addr=10)

    def test_add_resource_wrong_twice(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_resource("a", name="foo", size=16)
        with self.assertRaisesRegex(ValueError,
                r"Resource 'a' is already added at address range 0x0..0x10"):
            memory_map.add_resource("a", name="bar", size=16)

    def test_iter_resources(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        memory_map.add_resource("a", name="foo", size=1)
        memory_map.add_resource("b", name="bar", size=2)
        self.assertEqual(list(memory_map.resources()), [
            ("a", "foo", (0, 1)),
            ("b", "bar", (1, 3)),
        ])

    def test_add_window(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1), (0, 1))
        self.assertEqual(memory_map.add_window(MemoryMap(addr_width=10, data_width=8)),
                         (0x400, 0x800, 1))
        self.assertEqual(memory_map.add_resource("b", name="bar", size=1), (0x800, 0x801))

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

    def test_add_window_wrong_frozen(self):
        memory_map = MemoryMap(addr_width=2, data_width=8)
        memory_map.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen. Cannot add window "
                r"<nmigen_soc\.memory\.MemoryMap object at .+?>"):
            memory_map.add_window(MemoryMap(addr_width=1, data_width=8))

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

    def test_add_window_wrong_name_conflict(self):
        memory_map = MemoryMap(addr_width=2, data_width=8)
        memory_map.add_resource("a", name="foo", size=0)
        window = MemoryMap(addr_width=1, data_width=8, name="foo")
        with self.assertRaisesRegex(ValueError, r"Name foo is already used by 'a'"):
            memory_map.add_window(window)

    def test_add_window_wrong_name_conflict_subordinate(self):
        memory_map = MemoryMap(addr_width=2, data_width=8)
        memory_map.add_resource("a", name="foo", size=0)
        memory_map.add_resource("b", name="bar", size=0)
        window = MemoryMap(addr_width=1, data_width=8, name=None)
        window.add_resource("c", name="foo", size=0)
        window.add_resource("d", name="bar", size=0)
        with self.assertRaisesRegex(ValueError,
                r"The following names are already used: "
                r"bar is used by 'b'; "
                r"foo is used by 'a'"):
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
        self.assertEqual(memory_map.add_resource("a", name="foo", size=1), (0, 1))
        self.assertEqual(memory_map.align_to(10), 0x400)
        self.assertEqual(memory_map.add_resource("b", name="bar", size=16), (0x400, 0x410))

    def test_align_to_wrong(self):
        memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Alignment must be a non-negative integer, not -1"):
            memory_map.align_to(alignment=-1)


class MemoryMapDiscoveryTestCase(unittest.TestCase):
    def setUp(self):
        self.root = MemoryMap(addr_width=32, data_width=32)
        self.res1 = "res1"
        self.root.add_resource(self.res1, name="name1", size=16)
        self.win1 = MemoryMap(addr_width=16, data_width=32)
        self.res2 = "res2"
        self.win1.add_resource(self.res2, name="name2", size=32)
        self.res3 = "res3"
        self.win1.add_resource(self.res3, name="name3", size=32)
        self.root.add_window(self.win1)
        self.res4 = "res4"
        self.root.add_resource(self.res4, name="name4", size=1)
        self.win2 = MemoryMap(addr_width=16, data_width=8)
        self.res5 = "res5"
        self.win2.add_resource(self.res5, name="name5", size=16)
        self.root.add_window(self.win2, sparse=True)
        self.win3 = MemoryMap(addr_width=16, data_width=8, name="win3")
        self.res6 = "res6"
        self.win3.add_resource(self.res6, name="name6", size=16)
        self.root.add_window(self.win3, sparse=False)

    def test_iter_all_resources(self):
        res_info = list(self.root.all_resources())

        self.assertIs(res_info[0].resource, self.res1)
        self.assertEqual(res_info[0].name,  ("name1",))
        self.assertEqual(res_info[0].start, 0x00000000)
        self.assertEqual(res_info[0].end,   0x00000010)
        self.assertEqual(res_info[0].width, 32)

        self.assertIs(res_info[1].resource, self.res2)
        self.assertEqual(res_info[1].name,  ("name2",))
        self.assertEqual(res_info[1].start, 0x00010000)
        self.assertEqual(res_info[1].end,   0x00010020)
        self.assertEqual(res_info[1].width, 32)

        self.assertIs(res_info[2].resource, self.res3)
        self.assertEqual(res_info[2].name,  ("name3",))
        self.assertEqual(res_info[2].start, 0x00010020)
        self.assertEqual(res_info[2].end,   0x00010040)
        self.assertEqual(res_info[2].width, 32)

        self.assertIs(res_info[3].resource, self.res4)
        self.assertEqual(res_info[3].name,  ("name4",))
        self.assertEqual(res_info[3].start, 0x00020000)
        self.assertEqual(res_info[3].end,   0x00020001)
        self.assertEqual(res_info[3].width, 32)

        self.assertIs(res_info[4].resource, self.res5)
        self.assertEqual(res_info[4].name,  ("name5",))
        self.assertEqual(res_info[4].start, 0x00030000)
        self.assertEqual(res_info[4].end,   0x00030010)
        self.assertEqual(res_info[4].width, 8)

        self.assertIs(res_info[5].resource, self.res6)
        self.assertEqual(res_info[5].name,  ("win3", "name6"))
        self.assertEqual(res_info[5].start, 0x00040000)
        self.assertEqual(res_info[5].end,   0x00040004)
        self.assertEqual(res_info[5].width, 32)

    def test_find_resource(self):
        for res_info in self.root.all_resources():
            other = self.root.find_resource(res_info.resource)
            self.assertIs(other.resource, res_info.resource)
            self.assertEqual(other.name,  res_info.name)
            self.assertEqual(other.start, res_info.start)
            self.assertEqual(other.end,   res_info.end)
            self.assertEqual(other.width, res_info.width)

    def test_find_resource_wrong(self):
        with self.assertRaises(KeyError) as error:
            self.root.find_resource("resNA")
        self.assertEqual(error.exception.args, ("resNA",))

    def test_decode_address(self):
        for res_info in self.root.all_resources():
            self.assertEqual(self.root.decode_address(res_info.start),   res_info.resource)
            self.assertEqual(self.root.decode_address(res_info.end - 1), res_info.resource)

    def test_decode_address_missing(self):
        self.assertIsNone(self.root.decode_address(address=0x00000100))
