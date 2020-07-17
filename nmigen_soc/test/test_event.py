# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.back.pysim import *

from ..event import *


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd(vcd_file=open("test.vcd", "w")):
        sim.run()


class SourceTestCase(unittest.TestCase):
    def test_level(self):
        src = Source(trigger="level")
        self.assertEqual(src.trigger, Source.Trigger.LEVEL)

    def test_rise(self):
        src = Source(trigger="rise")
        self.assertEqual(src.trigger, Source.Trigger.RISE)

    def test_fall(self):
        src = Source(trigger="fall")
        self.assertEqual(src.trigger, Source.Trigger.FALL)

    def test_trigger_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Invalid trigger mode 'foo'; must be one of level, rise, fall"):
            src = Source(trigger="foo")

    def test_get_map_wrong(self):
        src = Source()
        with self.assertRaisesRegex(NotImplementedError,
                r"Event source \(rec src i trg\) does not have an event map"):
            src.event_map

    def test_get_map_frozen(self):
        src = Source()
        src.event_map = EventMap()
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen. Cannot add source."):
            src.event_map.add(Source())

    def test_set_map_wrong(self):
        src = Source()
        with self.assertRaisesRegex(TypeError,
                r"Event map must be an instance of EventMap, not 'foo'"):
            src.event_map = "foo"


class EventMapTestCase(unittest.TestCase):
    def test_add(self):
        src_0 = Source()
        src_1 = Source()
        event_map = EventMap()
        event_map.add(src_0)
        event_map.add(src=src_1)
        self.assertTrue(src_0 in event_map._sources)
        self.assertTrue(src_1 in event_map._sources)

    def test_add_wrong(self):
        event_map = EventMap()
        with self.assertRaisesRegex(TypeError,
                r"Event source must be an instance of event.Source, not 'foo'"):
            event_map.add("foo")

    def test_add_wrong_frozen(self):
        event_map = EventMap()
        event_map.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen. Cannot add source."):
            event_map.add(Source())

    def test_size(self):
        event_map = EventMap()
        event_map.add(Source())
        event_map.add(Source())
        self.assertEqual(event_map.size, 2)

    def test_index(self):
        src_0 = Source()
        src_1 = Source()
        event_map = EventMap()
        event_map.add(src_0)
        event_map.add(src_1)
        self.assertEqual(event_map.index(src_0), 0)
        self.assertEqual(event_map.index(src=src_1), 1)

    def test_index_add_twice(self):
        src = Source()
        event_map = EventMap()
        event_map.add(src)
        event_map.add(src)
        self.assertEqual(event_map.index(src), 0)
        self.assertEqual(event_map.size, 1)

    def test_index_wrong(self):
        event_map = EventMap()
        with self.assertRaisesRegex(TypeError,
                r"Event source must be an instance of event.Source, not 'foo'"):
            event_map.index("foo")

    def test_index_not_found(self):
        src = Source()
        event_map = EventMap()
        with self.assertRaises(KeyError):
            event_map.index(src)

    def test_iter_sources(self):
        src_0 = Source()
        src_1 = Source()
        event_map = EventMap()
        event_map.add(src_0)
        event_map.add(src_1)
        self.assertEqual(list(event_map.sources()), [
            (src_0, 0),
            (src_1, 1),
        ])


class MonitorTestCase(unittest.TestCase):
    def test_simple(self):
        sub_0 = Source()
        sub_1 = Source()
        event_map = EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        dut = Monitor(event_map, trigger="rise")
        self.assertIs(dut.src.event_map, event_map)
        self.assertEqual(dut.src.trigger, Source.Trigger.RISE)
        self.assertEqual(dut.enable.width, 2)
        self.assertEqual(dut.pending.width, 2)
        self.assertEqual(dut.clear.width, 2)

    def test_event_map_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Event map must be an instance of EventMap, not 'foo'"):
            dut = Monitor(event_map="foo")

    def test_events(self):
        sub_0 = Source(trigger="level")
        sub_1 = Source(trigger="rise")
        sub_2 = Source(trigger="fall")
        event_map = EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        event_map.add(sub_2)
        dut = Monitor(event_map)

        def process():
            yield sub_0.i.eq(1)
            yield sub_1.i.eq(0)
            yield sub_2.i.eq(1)
            yield
            self.assertEqual((yield sub_0.trg), 1)
            self.assertEqual((yield sub_1.trg), 0)
            self.assertEqual((yield sub_2.trg), 0)
            yield
            self.assertEqual((yield dut.pending), 0b001)
            self.assertEqual((yield dut.src.i), 0)

            yield dut.enable.eq(0b111)
            yield
            self.assertEqual((yield dut.src.i), 1)

            yield dut.clear.eq(0b001)
            yield
            self.assertEqual((yield dut.pending), 0b001)
            self.assertEqual((yield dut.src.i), 1)

            yield sub_0.i.eq(0)
            yield
            self.assertEqual((yield sub_0.trg), 0)
            self.assertEqual((yield sub_1.trg), 0)
            self.assertEqual((yield sub_2.trg), 0)
            yield
            self.assertEqual((yield dut.pending), 0b000)
            self.assertEqual((yield dut.src.i), 0)

            yield sub_1.i.eq(1)
            yield
            self.assertEqual((yield sub_0.trg), 0)
            self.assertEqual((yield sub_1.trg), 1)
            self.assertEqual((yield sub_2.trg), 0)
            yield
            self.assertEqual((yield dut.pending), 0b010)
            self.assertEqual((yield dut.src.i), 1)

            yield sub_2.i.eq(0)
            yield
            self.assertEqual((yield sub_0.trg), 0)
            self.assertEqual((yield sub_1.trg), 0)
            self.assertEqual((yield sub_2.trg), 1)
            yield
            self.assertEqual((yield dut.pending), 0b110)
            self.assertEqual((yield dut.src.i), 1)

            yield dut.clear.eq(0b110)
            yield
            self.assertEqual((yield sub_0.trg), 0)
            self.assertEqual((yield sub_1.trg), 0)
            self.assertEqual((yield sub_2.trg), 0)
            yield
            self.assertEqual((yield dut.pending), 0b000)
            self.assertEqual((yield dut.src.i), 0)

        simulation_test(dut, process)
