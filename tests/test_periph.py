import unittest

from amaranth_soc.periph import *
from amaranth_soc.memory import MemoryMap
from amaranth_soc import event


class ConstantBoolTestCase(unittest.TestCase):
    def test_init(self):
        a = ConstantBool(True)
        b = ConstantBool(False)
        self.assertTrue(a.value)
        self.assertFalse(b.value)

    def test_value_wrong(self):
        with self.assertRaisesRegex(TypeError, r"Value must be a bool, not 'foo'"):
            ConstantBool("foo")

    def test_repr(self):
        self.assertEqual(repr(ConstantBool(True)), "ConstantBool(True)")


class ConstantIntTestCase(unittest.TestCase):
    def test_init(self):
        c = ConstantInt(5, width=8, signed=True)
        self.assertEqual(c.value,  5)
        self.assertEqual(c.width,  8)
        self.assertEqual(c.signed, True)

    def test_init_default(self):
        c = ConstantInt(5)
        self.assertEqual(c.value,  5)
        self.assertEqual(c.width,  3)
        self.assertEqual(c.signed, False)

    def test_value_wrong(self):
        with self.assertRaisesRegex(TypeError, r"Value must be an integer, not 'foo'"):
            ConstantInt("foo")

    def test_width_wrong(self):
        with self.assertRaisesRegex(TypeError, r"Width must be an integer, not 'foo'"):
            ConstantInt(5, width="foo")

    def test_width_overflow(self):
        with self.assertRaisesRegex(ValueError,
                r"Width must be greater than or equal to the number of bits needed to represent 5"):
            ConstantInt(5, width=1)

    def test_signed_wrong(self):
        with self.assertRaisesRegex(TypeError, r"Signedness must be a bool, not 'foo'"):
            ConstantInt(5, signed="foo")

    def test_repr(self):
        self.assertEqual(
            repr(ConstantInt(-5, width=8, signed=True)),
            "ConstantInt(-5, width=8, signed=True)"
        )


class ConstantMapTestCase(unittest.TestCase):
    def test_init(self):
        constant_map = ConstantMap(A=5, B=True, C=ConstantBool(False))
        self.assertEqual(
            repr(constant_map), "ConstantMap(["
            "('A', ConstantInt(5, width=3, signed=False)), "
            "('B', ConstantBool(True)), "
            "('C', ConstantBool(False))])",
        )

    def test_init_wrong_value(self):
        with self.assertRaisesRegex(TypeError,
                r"Constant value must be an instance of ConstantValue, not \('foo', 'bar'\)"):
            ConstantMap(A=("foo", "bar"))

    def test_getitem(self):
        a = ConstantInt(1)
        b = ConstantBool(False)
        constant_map = ConstantMap(A=a, B=b)
        self.assertIs(constant_map["A"], a)
        self.assertIs(constant_map["B"], b)

    def test_iter(self):
        a = ConstantInt(1)
        b = ConstantBool(False)
        constant_map = ConstantMap(B=b, A=a)
        self.assertEqual(list(constant_map.items()), [
            ("B", b),
            ("A", a),
        ])

    def test_len(self):
        a = ConstantInt(1)
        b = ConstantBool(False)
        constant_map = ConstantMap(B=b, A=a)
        self.assertEqual(len(constant_map), 2)


class PeripheralInfoTestCase(unittest.TestCase):
    def test_memory_map(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map)
        self.assertIs(info.memory_map, memory_map)

    def test_memory_map_frozen(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen. Cannot add resource 'a'"):
            memory_map.add_resource("a", name="foo", size=3)

    def test_memory_map_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            info = PeripheralInfo(memory_map="foo")

    def test_irq(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        irq = event.Source.Signature().create(path=("irq",))
        info = PeripheralInfo(memory_map=memory_map, irq=irq)
        self.assertIs(info.irq, irq)

    def test_irq_none(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map, irq=None)
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral info does not have an IRQ line"):
            info.irq

    def test_irq_default(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map)
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral info does not have an IRQ line"):
            info.irq

    def test_irq_wrong(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"IRQ line must be an instance of event.Source, not 'foo'"):
            info = PeripheralInfo(memory_map=memory_map, irq="foo")

    def test_constant_map(self):
        constant_map = ConstantMap()
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map, constant_map=constant_map)
        self.assertIs(info.constant_map, constant_map)

    def test_constant_map_none(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map, constant_map=None)
        self.assertIsInstance(info.constant_map, ConstantMap)
        self.assertEqual(info.constant_map, {})

    def test_constant_map_default(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map)
        self.assertIsInstance(info.constant_map, ConstantMap)
        self.assertEqual(info.constant_map, {})

    def test_constant_map_wrong(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        with self.assertRaisesRegex(TypeError,
                r"Constant map must be an instance of ConstantMap, not 'foo'"):
            info = PeripheralInfo(memory_map=memory_map, constant_map="foo")
