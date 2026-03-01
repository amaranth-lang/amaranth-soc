Wishbone bus
============

.. warning::

   This manual is a work in progress and is seriously incomplete!

.. py:module:: amaranth_soc.wishbone.bus

The :mod:`amaranth_soc.wishbone.bus` module provides Wishbone bus primitives.

.. autoclass:: CycleType()
   :no-members:

   .. autoattribute:: CLASSIC
   .. autoattribute:: CONST_BURST
   .. autoattribute:: INCR_BURST
   .. autoattribute:: END_OF_BURST

.. autoclass:: BurstTypeExt()
   :no-members:

   .. autoattribute:: LINEAR
   .. autoattribute:: WRAP_4
   .. autoattribute:: WRAP_8
   .. autoattribute:: WRAP_16

.. autoclass:: Feature()
   :no-members:

   .. autoattribute:: ERR
   .. autoattribute:: RTY
   .. autoattribute:: STALL
   .. autoattribute:: LOCK
   .. autoattribute:: CTI
   .. autoattribute:: BTE

.. autoclass:: Signature()
   :no-members:

   .. autoattribute:: addr_width
   .. autoattribute:: data_width
   .. autoattribute:: granularity
   .. autoattribute:: features
   .. automethod:: create
   .. automethod:: __eq__


.. autoclass:: Interface()
   :no-members:

   .. autoattribute:: addr_width
   .. autoattribute:: data_width
   .. autoattribute:: granularity
   .. autoattribute:: features
   .. autoattribute:: memory_map

.. autoclass:: Decoder()
   :no-members:

   .. automethod:: align_to
   .. automethod:: add

.. autoclass:: Arbiter()
   :no-members:

   .. automethod:: add
