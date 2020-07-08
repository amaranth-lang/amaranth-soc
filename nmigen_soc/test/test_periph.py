import unittest

from ..periph import PeripheralInfo
from ..memory import MemoryMap
from .. import event


class PeripheralInfoTestCase(unittest.TestCase):
    def test_memory_map(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map)
        self.assertIs(info.memory_map, memory_map)

    def test_memory_map_frozen(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        info = PeripheralInfo(memory_map=memory_map)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen. Address width cannot be extended further"):
            memory_map.add_resource("a", size=3, extend=True)

    def test_memory_map_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            info = PeripheralInfo(memory_map="foo")

    def test_irq(self):
        memory_map = MemoryMap(addr_width=1, data_width=8)
        irq = event.Source()
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
