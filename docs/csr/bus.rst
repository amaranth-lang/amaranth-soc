CSR bus primitives
------------------

.. warning::

   This manual is a work in progress and is seriously incomplete!

.. py:module:: amaranth_soc.csr.bus

The :mod:`amaranth_soc.csr.bus` module provides CSR bus primitives.

.. autoclass:: amaranth_soc.csr.bus::Element.Access()
   :no-members:

   .. autoattribute:: amaranth_soc.csr.bus::Element.Access.R
   .. autoattribute:: amaranth_soc.csr.bus::Element.Access.W
   .. autoattribute:: amaranth_soc.csr.bus::Element.Access.RW
   .. automethod:: amaranth_soc.csr.bus::Element.Access.readable
   .. automethod:: amaranth_soc.csr.bus::Element.Access.writable

.. autoclass:: amaranth_soc.csr.bus::Element.Signature()
   :no-members:

   .. autoattribute:: amaranth_soc.csr.bus::Element.Signature.width
   .. autoattribute:: amaranth_soc.csr.bus::Element.Signature.access
   .. automethod:: amaranth_soc.csr.bus::Element.Signature.create
   .. automethod:: amaranth_soc.csr.bus::Element.Signature.__eq__

.. autoclass:: Element()
   :no-members:

   .. autoattribute:: width
   .. autoattribute:: access

.. autoclass:: Signature()
   :no-members:

   .. autoattribute:: addr_width
   .. autoattribute:: data_width
   .. automethod:: create
   .. automethod:: __eq__

.. autoclass:: Interface()
   :no-members:

   .. autoattribute:: addr_width
   .. autoattribute:: data_width
   .. autoattribute:: memory_map

.. autoclass:: Multiplexer()
   :no-members:

.. autoclass:: Decoder()
   :no-members:

   .. automethod:: align_to
   .. automethod:: add
