from amaranth import *
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out


__all__ = ["Source", "EventMap", "Monitor"]


class Source(wiring.PureInterface):
    class Trigger(enum.Enum):
        """Event trigger mode."""
        LEVEL = "level"
        RISE  = "rise"
        FALL  = "fall"

    class Signature(wiring.Signature):
        """Event source signature.

        Parameters
        ----------
        trigger : :class:`Source.Trigger`
            Trigger mode. An event can be edge- or level-triggered by the input line.

        Interface attributes
        --------------------
        i : Signal()
            Input line. Sampled in order to detect an event.
        trg : Signal()
            Event trigger. Asserted when an event occurs, according to the trigger mode.
        """
        def __init__(self, *, trigger="level"):
            super().__init__({
                "i":   Out(1),
                "trg": In(1),
            })
            self._trigger = Source.Trigger(trigger)

        @property
        def trigger(self):
            return self._trigger

        def create(self, *, path=None, src_loc_at=0):
            """Create a compatible interface.

            See :meth:`wiring.Signature.create` for details.

            Returns
            -------
            A :class:`Source` object using this signature.
            """
            return Source(trigger=self.trigger, path=path, src_loc_at=1 + src_loc_at)

        def __eq__(self, other):
            """Compare signatures.

            Two signatures are equal if they have the same trigger mode.
            """
            return isinstance(other, Source.Signature) and self.trigger == other.trigger

        def __repr__(self):
            return f"event.Source.Signature({self.members!r})"

    """Event source interface.

    Parameters
    ----------
    trigger : :class:`Source.Trigger`
        Trigger mode. An event can be edge- or level-triggered by the input line.
    path : iter(:class:`str`)
        Path to this event source interface. Optional. See :class:`wiring.PureInterface`.

    Attributes
    ----------
    event_map : :class:`EventMap`
        A collection of event sources.
    """
    def __init__(self, *, trigger="level", path=None, src_loc_at=0):
        super().__init__(Source.Signature(trigger=trigger), path=path, src_loc_at=1 + src_loc_at)
        self._event_map = None

    @property
    def trigger(self):
        return self.signature.trigger

    @property
    def event_map(self):
        if self._event_map is None:
            raise AttributeError(f"{self!r} does not have an event map")
        return self._event_map

    @event_map.setter
    def event_map(self, event_map):
        if not isinstance(event_map, EventMap):
            raise TypeError(f"Event map must be an instance of EventMap, not {event_map!r}")
        event_map.freeze()
        self._event_map = event_map

    def __repr__(self):
        return f"event.Source({self.signature!r})"


class EventMap:
    """Event map.

    An event map is a description of a set of events. It is built by adding event sources
    and can be queried later to determine their index. Event indexing is done implicitly by
    increment, starting at 0.
    """
    def __init__(self):
        self._sources = dict()
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
            raise ValueError("Event map has been frozen. Cannot add source")
        if not isinstance(src, Source):
            raise TypeError(f"Event source must be an instance of event.Source, not {src!r}")
        if id(src) not in self._sources:
            self._sources[id(src)] = src, self.size

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
            raise TypeError(f"Event source must be an instance of event.Source, not {src!r}")
        _, index = self._sources[id(src)]
        return index

    def sources(self):
        """Iterate event sources.

        Yield values
        ------------
        A tuple ``src, index`` corresponding to an event source and its index.
        """
        yield from self._sources.values()


class Monitor(wiring.Component):
    """Event monitor.

    A monitor for subordinate event sources.

    Parameters
    ----------
    event_map : :class:`EventMap`
        A collection of event sources.
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
        if not isinstance(event_map, EventMap):
            raise TypeError(f"Event map must be an instance of EventMap, not {event_map!r}")
        super().__init__({
            "src":     Out(Source.Signature(trigger=trigger)),
            "enable":  In(event_map.size),
            "pending": In(event_map.size),
            "clear":   In(event_map.size),
        })
        self.src.event_map = event_map

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
