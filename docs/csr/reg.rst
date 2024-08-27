CSR registers
-------------

.. py:module:: amaranth_soc.csr.reg

The :mod:`amaranth_soc.csr.reg` module provides a way to define and create CSR registers and register fields.

.. testsetup::

   from amaranth import *
   from amaranth.lib import wiring
   from amaranth.lib.wiring import In, Out, flipped, connect

   from amaranth_soc import csr
   from amaranth_soc.memory import *

Introduction
============

Control and Status registers are commonly used as an interface between SoC peripherals and the firmware that operates them.

This module provides the following functionality:

1. Register field description and implementation via the :class:`Field` and :class:`FieldAction` classes. The :mod:`amaranth_soc.csr.action` module provides a built-in :class:`FieldAction` subclasses for common use cases. If needed, users can implement their own subclasses.
2. Composable layouts of register fields via :class:`FieldActionMap` and :class:`FieldActionArray`. These classes are not meant to be instantiated directly, but are useful when introspecting the layout of a register.
3. Register definitions via the :class:`Register` class. The fields of a register can be provided as :term:`variable annotations <python:variable annotation>` or as instance parameters.
4. A :class:`Builder` class to organize registers of a peripheral into a hierarchy of clusters and arrays, to be converted into a :class:`~amaranth_soc.memory.MemoryMap`.
5. A bridge between a CSR bus interface and the registers of a peripheral, via the :class:`Bridge` class.

Examples
========

Defining a register declaratively
+++++++++++++++++++++++++++++++++

If its layout and access mode are known in advance, a register can be concisely defined using :term:`variable annotations <python:variable annotation>`:

.. testcode::

   class Status(csr.Register, access="rw"):
       rdy:    csr.Field(csr.action.R,       1)
       err:    csr.Field(csr.action.RW1C,    1)
       _unimp: csr.Field(csr.action.ResR0W0, 6)

.. note::

   By convention, names of :ref:`reserved fields <csr-action-reserved>` (such as ``_unimp`` in the above example) should begin with an underscore.

Defining a register with instance parameters
++++++++++++++++++++++++++++++++++++++++++++

If the layout or access mode of a register aren't known until instantiation, a :class:`Register` subclass can override them in ``__init__``:

.. testcode::

   class Data(csr.Register):
       def __init__(self, width=8, access="w"):
           super().__init__(fields={"data": csr.Field(csr.action.W, width)},
                            access=access)

Defining a single-field register
++++++++++++++++++++++++++++++++

In the previous example, the ``Data`` register has a single field named ``"Data.data"``, which is redundant.

If no other fields are expected to be added in future revisions of the peripheral (or forward compatibility is not a concern), the field name can be omitted like so:

.. testcode::

   class Data(csr.Register, access="w"):
       def __init__(self):
           super().__init__(csr.Field(csr.action.W, 8))


Defining a register with nested fields
++++++++++++++++++++++++++++++++++++++

Hierarchical layouts of register fields can be expressed using lists and dicts:

.. testcode::

   class SetClr(csr.Register, access="r"):
       pin: [{"set": csr.Field(csr.action.W, 1),
              "clr": csr.Field(csr.action.W, 1)} for _ in range(8)]


Connecting registers to a CSR bus
+++++++++++++++++++++++++++++++++

In this example, the registers of ``FooPeripheral`` are added to a :class:`Builder` to produce a memory map, and then bridged to a bus interface:

.. testcode::

   class FooPeripheral(wiring.Component):
       class Ctrl(csr.Register, access="rw"):
           enable: csr.Field(csr.action.RW, 1)
           _unimp: csr.Field(csr.action.ResR0W0, 7)

       class Data(csr.Register, access="r"):
           def __init__(self, width):
               super().__init__(csr.Field(csr.action.R, width))

       def __init__(self):
           regs = csr.Builder(addr_width=4, data_width=8)

           reg_ctrl = regs.add("Ctrl", Ctrl())
           reg_data = regs.add("Data", Data(width=32), offset=4)

           self._bridge = csr.Bridge(regs.as_memory_map())

           super().__init__({"csr_bus": In(csr.Signature(addr_width=4, data_width=8))})
           self.csr_bus.memory_map = self._bridge.bus.memory_map

       def elaborate(self, platform):
           return Module() # ...


Defining a custom field action
++++++++++++++++++++++++++++++

If :mod:`amaranth_soc.csr.action` built-ins do not cover a desired use case, a custom :class:`FieldAction` may provide an alternative.

This example shows a "read/write-0-to-set" field action:

.. testcode::

   class RW0S(csr.FieldAction):
       def __init__(self, shape, init=0):
           super().__init__(shape, access="rw", members={
               "data":  Out(shape),
               "clear": In(shape),
           })
           self._storage = Signal(shape, init=init)
           self._init    = init

       @property
       def init(self):
           return self._init

       def elaborate(self, platform):
           m = Module()

           for i, storage_bit in enumerate(self._storage):
               with m.If(self.clear[i]):
                   m.d.sync += storage_bit.eq(0)
               with m.If(self.port.w_stb & ~self.port.w_data[i]):
                   m.d.sync += storage_bit.eq(1)

           m.d.comb += [
               self.port.r_data.eq(self._storage),
               self.data.eq(self._storage),
           ]

           return m


``RW0S`` can then be passed to :class:`Field`:

.. testcode::

   class Foo(csr.Register, access="rw"):
       mask: csr.Field(RW0S, 8)
       data: csr.Field(csr.action.RW, 8)


Fields
======

.. autoclass:: amaranth_soc.csr.reg::FieldPort.Access()
   :no-members:

   .. autoattribute:: amaranth_soc.csr.reg::FieldPort.Access.R
   .. autoattribute:: amaranth_soc.csr.reg::FieldPort.Access.W
   .. autoattribute:: amaranth_soc.csr.reg::FieldPort.Access.RW
   .. autoattribute:: amaranth_soc.csr.reg::FieldPort.Access.NC
   .. automethod:: amaranth_soc.csr.reg::FieldPort.Access.readable
   .. automethod:: amaranth_soc.csr.reg::FieldPort.Access.writable

.. autoclass:: amaranth_soc.csr.reg::FieldPort.Signature()
   :no-members:

   .. automethod:: amaranth_soc.csr.reg::FieldPort.Signature.create
   .. automethod:: amaranth_soc.csr.reg::FieldPort.Signature.__eq__

.. autoclass:: FieldPort()
   :no-members:

.. autoclass:: Field()
   :no-members:

   .. automethod:: create

Field actions
=============

.. autoclass:: FieldAction()
   :no-members:

.. autoclass:: FieldActionMap()
   :no-members:

   .. automethod:: __getitem__
   .. automethod:: __getattr__
   .. automethod:: __iter__
   .. automethod:: __len__
   .. automethod:: flatten

.. autoclass:: FieldActionArray()
   :no-members:

   .. automethod:: __getitem__
   .. automethod:: __len__
   .. automethod:: flatten

Registers
=========

.. autoclass:: Register()
   :no-members:

   .. autoattribute:: field
   .. autoattribute:: f
   .. automethod:: __iter__

.. autoclass:: Builder()
   :no-members:

   .. automethod:: freeze
   .. automethod:: add
   .. automethod:: Cluster
   .. automethod:: Index
   .. automethod:: as_memory_map

.. autoclass:: Bridge()
   :no-members:
