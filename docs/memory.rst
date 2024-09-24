Memory maps
###########

.. py:module:: amaranth_soc.memory

The :mod:`amaranth_soc.memory` module provides primitives for organizing the address space of a bus interface.

.. testsetup::

   from amaranth import *

   from amaranth_soc import csr
   from amaranth_soc.memory import *

.. _memory-introduction:

Introduction
============

The purpose of :class:`MemoryMap` is to provide a hierarchical description of the address space of a System-on-Chip, from its bus interconnect to the registers of its peripherals. It is composed of :ref:`resources <memory-resources>` (representing registers, memories, etc) and :ref:`windows <memory-windows>` (representing bus bridges), and may be :ref:`queried <memory-accessing-windows>` afterwards in order to enumerate its contents, or determine the address of a resource.

.. _memory-resources:

Resources
=========

A *resource* is a :class:`~amaranth.lib.wiring.Component` previously added to a :class:`MemoryMap`. Each resource occupies an unique range of addresses within the memory map, and represents a device that is a target for bus transactions.

Adding resources
++++++++++++++++

Resources are added with :meth:`MemoryMap.add_resource`, which returns a ``(start, end)`` tuple describing their address range:

.. testcode::

   memory_map = MemoryMap(addr_width=3, data_width=8)

   reg_ctrl = csr.Register(csr.Field(csr.action.RW, 32), "rw")
   reg_data = csr.Register(csr.Field(csr.action.RW, 32), "rw")

.. doctest::

   >>> memory_map.add_resource(reg_ctrl, size=4, addr=0x0, name=("ctrl",))
   (0, 4)
   >>> memory_map.add_resource(reg_data, size=4, addr=0x4, name=("data",))
   (4, 8)

.. _memory-implicit-next-address:

.. note::

   The ``addr`` parameter of :meth:`MemoryMap.add_resource` and :meth:`MemoryMap.add_window` is optional.

   To simplify address assignment, each :class:`MemoryMap` has an *implicit next address*, starting at 0. If a resource or a window is added without an explicit address, the implicit next address is used. In any case, the implicit next address is set to the address immediately following the newly added resource or window.

Accessing resources
+++++++++++++++++++

Memory map resources can be iterated with :meth:`MemoryMap.resources`:

.. doctest::

   >>> for resource, name, (start, end) in memory_map.resources():
   ...     print(f"name={name}, start={start:#x}, end={end:#x}, resource={resource}")
   name=Name('ctrl'), start=0x0, end=0x4, resource=<...>
   name=Name('data'), start=0x4, end=0x8, resource=<...>

A memory map can be queried with :meth:`MemoryMap.find_resource` to get the name and address range of a given resource:

.. doctest::

   >>> memory_map.find_resource(reg_ctrl)
   ResourceInfo(path=(Name('ctrl'),), start=0x0, end=0x4, width=8)

The resource located at a given address can be retrieved with :meth:`MemoryMap.decode_address`:

.. doctest::

   >>> memory_map.decode_address(0x4) is reg_data
   True


.. _memory-alignment:

Alignment
=========

The value of :attr:`MemoryMap.alignment` constrains the layout of a memory map. If unspecified, it defaults to 0.

Each resource or window added to a memory map is placed at an address that is a multiple of ``2 ** alignment``, and its size is rounded up to a multiple of ``2 ** alignment``.

For example, the resources of this memory map are 64-bit aligned:

.. testcode::

   memory_map = MemoryMap(addr_width=8, data_width=8, alignment=3)

   reg_foo = csr.Register(csr.Field(csr.action.RW, 32), "rw")
   reg_bar = csr.Register(csr.Field(csr.action.RW, 32), "rw")
   reg_baz = csr.Register(csr.Field(csr.action.RW, 32), "rw")

.. doctest::

   >>> memory_map.add_resource(reg_foo, size=4, name=("foo",))
   (0, 8)
   >>> memory_map.add_resource(reg_bar, size=4, name=("bar",), addr=0x9)
   Traceback (most recent call last):
   ...
   ValueError: Explicitly specified address 0x9 must be a multiple of 0x8 bytes

:meth:`MemoryMap.add_resource` takes an optional ``alignment`` parameter. If a value greater than :attr:`MemoryMap.alignment` is given, it becomes the alignment of this resource:

.. doctest::

   >>> memory_map.add_resource(reg_bar, size=4, name=("bar",), alignment=4)
   (16, 32)

:meth:`MemoryMap.align_to` can be used to align the :ref:`implicit next address <memory-implicit-next-address>`. Its alignment is modified if a value greater than :attr:`MemoryMap.alignment` is given.

.. doctest::

   >>> memory_map.align_to(6)
   64
   >>> memory_map.add_resource(reg_baz, size=4, name=("baz",))
   (64, 72)

.. note:: :meth:`MemoryMap.align_to` has no effect on the size of the next resource or window.

.. _memory-windows:

Windows
=======

A *window* is a :class:`MemoryMap` nested inside another memory map. Each window occupies an unique range of addresses within the memory map, and represents a bridge to a subordinate bus.

Adding windows
++++++++++++++

Windows are added with :meth:`MemoryMap.add_window`, which returns a ``(start, end, ratio)`` tuple describing their address range:

.. testcode::

   reg_ctrl    = csr.Register(csr.Field(csr.action.RW, 32), "rw")
   reg_rx_data = csr.Register(csr.Field(csr.action.RW, 32), "rw")
   reg_tx_data = csr.Register(csr.Field(csr.action.RW, 32), "rw")

   memory_map = MemoryMap(addr_width=14, data_width=32)
   rx_window  = MemoryMap(addr_width=12, data_width=32)
   tx_window  = MemoryMap(addr_width=12, data_width=32)

.. doctest::

   >>> memory_map.add_resource(reg_ctrl, size=1, name=("ctrl",))
   (0, 1)

   >>> rx_window.add_resource(reg_rx_data, size=1, name=("data",))
   (0, 1)
   >>> memory_map.add_window(rx_window, name=("rx",))
   (4096, 8192, 1)

The third value returned by :meth:`MemoryMap.add_window` represents the number of addresses that are accessed in the bus described by ``rx_window`` for one transaction in the bus described by ``memory_map``. It is 1 in this case, as both busses have the same width.

.. doctest::

   >>> tx_window.add_resource(reg_tx_data, size=1, name=("data",))
   (0, 1)
   >>> memory_map.add_window(tx_window, name=("tx",))
   (8192, 12288, 1)

.. _memory-accessing-windows:

Accessing windows
-----------------

Memory map windows can be iterated with :meth:`MemoryMap.windows`:

.. doctest::

   >>> for window, name, (start, end, ratio) in memory_map.windows():
   ...     print(f"{name}, start={start:#x}, end={end:#x}, ratio={ratio}")
   Name('rx'), start=0x1000, end=0x2000, ratio=1
   Name('tx'), start=0x2000, end=0x3000, ratio=1

Windows can also be iterated with :meth:`MemoryMap.window_patterns`, which encodes their address ranges as bit patterns compatible with the :ref:`match operator <lang-matchop>` and the :ref:`Case block <lang-switch>`:

.. doctest::

   >>> for window, name, (pattern, ratio) in memory_map.window_patterns():
   ...     print(f"{name}, pattern='{pattern}', ratio={ratio}")
   Name('rx'), pattern='01------------', ratio=1
   Name('tx'), pattern='10------------', ratio=1

Memory map resources can be recursively iterated with :meth:`MemoryMap.all_resources`, which yields instances of :class:`ResourceInfo`:

.. doctest::

   >>> for res_info in memory_map.all_resources():
   ...     print(res_info)
   ResourceInfo(path=(Name('ctrl'),), start=0x0, end=0x1, width=32)
   ResourceInfo(path=(Name('rx'), Name('data')), start=0x1000, end=0x1001, width=32)
   ResourceInfo(path=(Name('tx'), Name('data')), start=0x2000, end=0x2001, width=32)

Address translation
+++++++++++++++++++

When a memory map resource is accessed through a window, address translation may happen in three different modes.

Transparent mode
----------------

In *transparent mode*, each transaction on the primary bus results in one transaction on the subordinate bus without loss of data. This mode is selected when :meth:`MemoryMap.add_window` is given ``sparse=None``, which will fail if the window and the memory map have a different data widths.

.. note::

   In practice, transparent mode is identical to other modes; it can only be used with equal data widths, which results in the same behavior regardless of the translation mode. However, it causes :meth:`MemoryMap.add_window` to fail if the data widths are different.

Sparse mode
-----------

In *sparse mode*, each transaction on the wide primary bus results in one transaction on the narrow subordinate bus. High data bits on the primary bus are ignored, and any contiguous resource on the subordinate bus becomes discontiguous on the primary bus. This mode is selected when :meth:`MemoryMap.add_window` is given ``sparse=True``.

Dense mode
----------

In *dense mode*, each transaction on the wide primary bus results in several transactions on the narrow subordinate bus, and any contiguous resource on the subordinate bus stays contiguous on the primary bus. This mode is selected when :meth:`MemoryMap.add_window` is given ``sparse=False``.

Freezing
========

The state of a memory map can become immutable by calling :meth:`MemoryMap.freeze`:

.. testcode::

   memory_map = MemoryMap(addr_width=3, data_width=8)

   reg_ctrl = csr.Register(csr.Field(csr.action.RW, 32), "rw")

.. doctest::

   >>> memory_map.freeze()
   >>> memory_map.add_resource(reg_ctrl, size=4, addr=0x0, name=("ctrl",))
   Traceback (most recent call last):
   ...
   ValueError: Memory map has been frozen. Cannot add resource <...>

It is recommended to freeze a memory map before passing it to external logic, as a preventive measure against TOCTTOU bugs.

.. autoclass:: MemoryMap()
   :no-members:

   .. automethod:: freeze
   .. automethod:: align_to
   .. automethod:: add_resource
   .. automethod:: resources
   .. automethod:: add_window
   .. automethod:: windows
   .. automethod:: window_patterns
   .. automethod:: all_resources
   .. automethod:: find_resource
   .. automethod:: decode_address

.. autoclass:: ResourceInfo()
   :no-members:
