Memory maps
===========

.. warning::

   This manual is a work in progress and is seriously incomplete!

.. py:module:: amaranth_soc.memory

The :mod:`amaranth_soc.memory` module provides primitives for organizing the address space of a bus interface.

.. autoclass:: MemoryMap()
   :no-members:

   .. autoattribute:: addr_width
   .. autoattribute:: data_width
   .. autoattribute:: alignment
   .. autoattribute:: name
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
