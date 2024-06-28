CSR registers
-------------

.. warning::

   This manual is a work in progress and is seriously incomplete!

.. py:module:: amaranth_soc.csr.reg

The :mod:`amaranth_soc.csr.reg` module provides CSR register primitives.

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

   .. autoattribute:: amaranth_soc.csr.reg::FieldPort.Signature.shape
   .. autoattribute:: amaranth_soc.csr.reg::FieldPort.Signature.access
   .. automethod:: amaranth_soc.csr.reg::FieldPort.Signature.create
   .. automethod:: amaranth_soc.csr.reg::FieldPort.Signature.__eq__

.. autoclass:: FieldPort()
   :no-members:

   .. autoattribute:: shape
   .. autoattribute:: access

.. autoclass:: Field()
   :no-members:

   .. automethod:: create

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

.. autoclass:: Register()
   :no-members:

   .. autoattribute:: field
   .. autoattribute:: f
   .. automethod:: __iter__

.. autoclass:: Builder()
   :no-members:

   .. autoattribute:: addr_width
   .. autoattribute:: data_width
   .. autoattribute:: granularity
   .. autoattribute:: name
   .. automethod:: freeze
   .. automethod:: add
   .. automethod:: Cluster
   .. automethod:: Index
   .. automethod:: as_memory_map

.. autoclass:: Bridge()
   :no-members:
