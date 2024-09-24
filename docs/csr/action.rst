CSR fields
----------

.. py:module:: amaranth_soc.csr.action

The :mod:`amaranth_soc.csr.action` module provides built-in :class:`~amaranth_soc.csr.reg.FieldAction` implementations intended for common use cases, which are split in three categories: :ref:`basic fields <csr-action-basic>` for numerical values, :ref:`flag fields <csr-action-flag>` for arrays of bits, and :ref:`reserved fields <csr-action-reserved>` to serve as placeholders for compatibility.

.. _csr-action-basic:

Basic fields
============

Such fields are either exclusively writable by a CSR bus initiator (e.g. :class:`W`, :class:`RW`) or the peripheral itself (e.g. :class:`R`). This effectively removes the possibility of a write conflict between a CSR bus initiator and the peripheral.

.. autoclass:: R()
.. autoclass:: W()
.. autoclass:: RW()

.. _csr-action-flag:

Flag fields
===========

Flag fields may be concurrently written by a CSR bus initiator and the peripheral. Each bit of a flag field may be set or cleared independently of others.

Suggested use cases
+++++++++++++++++++

- :class:`RW1C` flags may be used when a peripheral needs to notify the CPU of a given condition, such as an error or a pending interrupt. To acknowledge the notification, the CPU would then write 1 to the flag bit.

- :class:`RW1S` flags may be used for self-clearing bits, such as the enable bit of a one-shot timer. When the timer reaches its maximum value, it would automatically disable itself by clearing its enable bit.

- A pair of :class:`RW1C` and :class:`RW1S` flags may be used to target the same range of bits (e.g. that drives an array of GPIO pins). This allows a CSR bus initiator to set and clear bits in one write transaction (which is guaranteed to be atomic). If a single :class:`RW` field was used instead, a read-modify-write transaction would be needed, and would require locking to insure its atomicity in a multi-tasked environment.

.. autoclass:: RW1C()
.. autoclass:: RW1S()

.. _csr-action-reserved:

Reserved fields
===============

Reserved fields may be defined to provide placeholders for past, future or undocumented functions of a peripheral.

Suggested use cases
+++++++++++++++++++

Reserved for future use (as value)
..................................

A :class:`ResRAWL` field can be used as a placeholder to ensure forward compatibility of software binaries with future SoC revisions, where it may be replaced with a :ref:`basic field <csr-action-basic>`.

The value returned by reads (and written back) must have defined semantics (e.g. a no-op) that can be relied upon in future SoC revisions. When writing to this field, software drivers targeting the current SoC revision must set up an atomic read-modify-write transaction.

Reserved for future use (as flag)
.................................

If a field is expected to be implemented as a :ref:`flag <csr-action-flag>` in a future SoC revision, it can be defined as a :class:`ResRAW0` field in the current revision to ensure forward compatibility of software binaries.

Software drivers targeting the current SoC revision should ignore the value returned by reads. Writing a value of 0 must be a no-op if the field is implemented in a future SoC revision.

Defined but deprecated
......................

If a field was deprecated in a previous SoC revision, it can be replaced with a :class:`ResR0WA` field to ensure backward compatibility of software binaries.

The value of 0 returned by reads (and written back) must retain the semantics defined in the SoC revision where this field was deprecated.

Defined but unimplemented
.........................

If a field is only implemented in some variants of a peripheral, it can be replaced by a :class:`ResR0W0` field in the others.

.. autoclass:: ResRAW0()
.. autoclass:: ResRAWL()
.. autoclass:: ResR0WA()
.. autoclass:: ResR0W0()
