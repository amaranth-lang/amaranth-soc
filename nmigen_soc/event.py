import enum
from collections import OrderedDict

from nmigen import *


__all__ = ["Source", "EventMap", "Monitor"]


class Source(Record):
    class Trigger(enum.Enum):
        """Event trigger mode."""
        LEVEL = "level"
        RISE  = "rise"
        FALL  = "fall"

    """Event source interface.

    Parameters
    ----------
    trigger : :class:`Trigger`
        Trigger mode. An event can be edge- or level-triggered by the input line.
    name: str
        Name of the underlying record.

    Attributes
    ----------
    i : Signal()
        Input line. Sampled in order to detect an event.
    trg : Signal()
        Event trigger. Asserted when an event occurs, according to the trigger mode.
    """
    def __init__(self, *, trigger="level", name=None, src_loc_at=0):
        choices = ("level", "rise", "fall")
        if not isinstance(trigger, Source.Trigger) and trigger not in choices:
            raise ValueError("Invalid trigger mode {!r}; must be one of {}"
                             .format(trigger, ", ".join(choices)))
        self.trigger = Source.Trigger(trigger)
        self._map    = None

        super().__init__([
            ("i",   1),
            ("trg", 1),
        ], name=name, src_loc_at=1 + src_loc_at)

    @property
    def event_map(self):
        """Event map.

        Return value
        ------------
        A :class:`EventMap` describing subordinate event sources.

        Exceptions
        ----------
        Raises :exn:`NotImplementedError` if the source does not have an event map.
        """
        if self._map is None:
            raise NotImplementedError("Event source {!r} does not have an event map"
                                      .format(self))
        return self._map

    @event_map.setter
    def event_map(self, event_map):
        if not isinstance(event_map, EventMap):
            raise TypeError("Event map must be an instance of EventMap, not {!r}"
                            .format(event_map))
        event_map.freeze()
        self._map = event_map

    # FIXME: get rid of this
    __hash__ = object.__hash__


class EventMap:
    """Event map.

    An event map is a description of a set of events. It is built by adding event sources
    and can be queried later to determine their index. Event indexing is done implicitly by
    increment, starting at 0.
    """
    def __init__(self):
        self._sources = OrderedDict()
        self._frozen  = False

    @property
    def size(self):
        """Size of the event map.

        Return value
        ------------
        The number of event sources in the map.
        """
        return len(self._sources)

    def freeze(self):
        """Freeze the event map.

        Once the event map is frozen, sources cannot be added anymore.
        """
        self._frozen = True

    def add(self, src):
        """Add an event source.

        Arguments
        ---------
        src : :class:`Source`
            Event source.

        Exceptions
        ----------
        Raises :exn:`ValueError` if the event map is frozen.
        """
        if self._frozen:
            raise ValueError("Event map has been frozen. Cannot add source.")
        if not isinstance(src, Source):
            raise TypeError("Event source must be an instance of event.Source, not {!r}"
                            .format(src))
        if src not in self._sources:
            self._sources[src] = self.size

    def index(self, src):
        """Get the index corresponding to an event source.

        Arguments
        ---------
        src : :class:`Source`
            Event source.

        Return value
        ------------
        The index of the source.

        Exceptions
        ----------
        Raises :exn:`KeyError` if the source is not found.
        """
        if not isinstance(src, Source):
            raise TypeError("Event source must be an instance of event.Source, not {!r}"
                            .format(src))
        return self._sources[src]

    def sources(self):
        """Iterate event sources.

        Yield values
        ------------
        A tuple ``src, index`` corresponding to an event source and its index.
        """
        for src, index in self._sources.items():
            yield src, index


class Monitor(Elaboratable):
    """Event monitor.

    A monitor for subordinate event sources.

    Parameters
    ----------
    event_map : :class:`EventMap`
        Event map.
    trigger : :class:`Source.Trigger`
        Trigger mode. See :class:`Source`.

    Attributes
    ----------
    src : :class:`Source`
        Event source. Its input is asserted when a subordinate event is enabled and pending.
    enable : Signal(event_map.size), bit mask, in
        Enabled events.
    pending : Signal(event_map.size), bit mask, out
        Pending events.
    clear : Signal(event_map.size), bit mask, in
        Clear selected pending events.
    """
    def __init__(self, event_map, *, trigger="level"):
        self.src = Source(trigger=trigger)
        self.src.event_map = event_map

        self.enable  = Signal(event_map.size)
        self.pending = Signal(event_map.size)
        self.clear   = Signal(event_map.size)

    def elaborate(self, platform):
        m = Module()

        for sub, index in self.src.event_map.sources():
            if sub.trigger != Source.Trigger.LEVEL:
                sub_i_r = Signal.like(sub.i, name_suffix="_r")
                m.d.sync += sub_i_r.eq(sub.i)

            if sub.trigger == Source.Trigger.LEVEL:
                m.d.comb += sub.trg.eq(sub.i)
            elif sub.trigger == Source.Trigger.RISE:
                m.d.comb += sub.trg.eq(~sub_i_r &  sub.i)
            elif sub.trigger == Source.Trigger.FALL:
                m.d.comb += sub.trg.eq( sub_i_r & ~sub.i)
            else:
                assert False # :nocov:

            with m.If(sub.trg):
                m.d.sync += self.pending[index].eq(1)
            with m.Elif(self.clear[index]):
                m.d.sync += self.pending[index].eq(0)

        m.d.comb += self.src.i.eq((self.enable & self.pending).any())

        return m
