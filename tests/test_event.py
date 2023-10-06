# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.sim import *

from amaranth_soc import event


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd(vcd_file=open("test.vcd", "w")):
        sim.run()


class SourceSignatureTestCase(unittest.TestCase):
    def test_level(self):
        sig = event.Source.Signature(trigger="level")
        self.assertEqual(sig.trigger, event.Source.Trigger.LEVEL)

    def test_rise(self):
        sig = event.Source.Signature(trigger="rise")
        self.assertEqual(sig.trigger, event.Source.Trigger.RISE)

    def test_fall(self):
        sig = event.Source.Signature(trigger="fall")
        self.assertEqual(sig.trigger, event.Source.Trigger.FALL)

    def test_create(self):
        sig = event.Source.Signature(trigger="level")
        src = sig.create(path=("foo", "bar"))
        self.assertIsInstance(src, event.Source)
        self.assertEqual(src.trigger, event.Source.Trigger.LEVEL)
        self.assertEqual(src.trg.name, "foo__bar__trg")
        self.assertEqual(src.signature, sig)

    def test_eq(self):
        self.assertEqual(event.Source.Signature(trigger="level"), event.Source.Signature())
        self.assertEqual(event.Source.Signature(trigger="level"),
                         event.Source.Signature(trigger=event.Source.Trigger.LEVEL))
        # different trigger mode
        self.assertNotEqual(event.Source.Signature(trigger="level"),
                            event.Source.Signature(trigger="rise"))
        self.assertNotEqual(event.Source.Signature(trigger="level"),
                            event.Source.Signature(trigger="fall"))
        self.assertNotEqual(event.Source.Signature(trigger="rise"),
                            event.Source.Signature(trigger="fall"))

    def test_trigger_wrong(self):
        with self.assertRaisesRegex(ValueError, r"'foo' is not a valid Source.Trigger"):
            src = event.Source.Signature(trigger="foo")

    def test_set_map(self):
        sig = event.Source.Signature()
        event_map = event.EventMap()
        sig.event_map = event_map
        self.assertIs(sig.event_map, event_map)

    def test_get_map_none(self):
        sig = event.Source.Signature()
        with self.assertRaisesRegex(AttributeError,
                r"event\.Source\.Signature\(.*\) does not have an event map"):
            sig.event_map

    def test_set_map_frozen(self):
        sig = event.Source.Signature()
        sig.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Signature has been frozen\. Cannot set its event map"):
            sig.event_map = event.EventMap()

    def test_set_wrong_map(self):
        sig = event.Source.Signature()
        with self.assertRaisesRegex(TypeError,
                r"Event map must be an instance of EventMap, not 'foo'"):
            sig.event_map = "foo"


class SourceTestCase(unittest.TestCase):
    def test_simple(self):
        src = event.Source(trigger="level", path=("foo", "bar"))
        self.assertIsInstance(src, event.Source)
        self.assertEqual(src.trigger, event.Source.Trigger.LEVEL)
        self.assertEqual(src.trg.name, "foo__bar__trg")

    def test_map(self):
        event_map = event.EventMap()
        src = event.Source(event_map=event_map)
        self.assertIs(src.event_map, event_map)

    def test_get_map_none(self):
        src = event.Source()
        with self.assertRaisesRegex(AttributeError,
                r"event\.Source\.Signature\(.*\) does not have an event map"):
            src.event_map

    def test_get_map_frozen(self):
        src = event.Source(event_map=event.EventMap())
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen\. Cannot add source"):
            src.event_map.add(event.Source.Signature().create())

    def test_wrong_map(self):
        with self.assertRaisesRegex(TypeError,
                r"Event map must be an instance of EventMap, not 'foo'"):
            event.Source(event_map="foo")


class EventMapTestCase(unittest.TestCase):
    def test_add(self):
        src_0 = event.Source(path=("src_0",))
        src_1 = event.Source(path=("src_1",))
        event_map = event.EventMap()
        event_map.add(src_0)
        event_map.add(src=src_1)
        self.assertTrue(id(src_0) in event_map._sources)
        self.assertTrue(id(src_1) in event_map._sources)

    def test_add_wrong(self):
        event_map = event.EventMap()
        with self.assertRaisesRegex(TypeError,
                r"Event source must be an instance of event.Source, not 'foo'"):
            event_map.add("foo")

    def test_add_wrong_frozen(self):
        event_map = event.EventMap()
        event_map.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Event map has been frozen. Cannot add source"):
            event_map.add(event.Source.Signature().create())

    def test_size(self):
        event_map = event.EventMap()
        event_map.add(event.Source())
        event_map.add(event.Source())
        self.assertEqual(event_map.size, 2)

    def test_index(self):
        src_0 = event.Source(path=("src_0",))
        src_1 = event.Source(path=("src_1",))
        event_map = event.EventMap()
        event_map.add(src_0)
        event_map.add(src_1)
        self.assertEqual(event_map.index(src_0), 0)
        self.assertEqual(event_map.index(src=src_1), 1)

    def test_index_add_twice(self):
        src = event.Source(path=("src",))
        event_map = event.EventMap()
        event_map.add(src)
        event_map.add(src)
        self.assertEqual(event_map.index(src), 0)
        self.assertEqual(event_map.size, 1)

    def test_index_wrong(self):
        event_map = event.EventMap()
        with self.assertRaisesRegex(TypeError,
                r"Event source must be an instance of event.Source, not 'foo'"):
            event_map.index("foo")

    def test_index_not_found(self):
        src = event.Source(path=("src",))
        event_map = event.EventMap()
        with self.assertRaises(KeyError):
            event_map.index(src)

    def test_iter_sources(self):
        src_0 = event.Source(path=("src_0",))
        src_1 = event.Source(path=("src_1",))
        event_map = event.EventMap()
        event_map.add(src_0)
        event_map.add(src_1)
        self.assertEqual(list(event_map.sources()), [
            (src_0, 0),
            (src_1, 1),
        ])


class MonitorTestCase(unittest.TestCase):
    def test_simple(self):
        sub_0 = event.Source(path=("sub_0",))
        sub_1 = event.Source(path=("sub_1",))
        event_map = event.EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        dut = event.Monitor(event_map, trigger="rise")
        self.assertIs(dut.src.event_map, event_map)
        self.assertEqual(dut.src.trigger, event.Source.Trigger.RISE)
        self.assertEqual(dut.enable.width, 2)
        self.assertEqual(dut.pending.width, 2)
        self.assertEqual(dut.clear.width, 2)

    def test_event_map_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Event map must be an instance of EventMap, not 'foo'"):
            dut = event.Monitor(event_map="foo")

    def test_events(self):
        sub_0 = event.Source(trigger="level", path=("sub_0",))
        sub_1 = event.Source(trigger="rise",  path=("sub_1",))
        sub_2 = event.Source(trigger="fall",  path=("sub_2",))
        event_map = event.EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        event_map.add(sub_2)
        dut = event.Monitor(event_map)

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
