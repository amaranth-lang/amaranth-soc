GPIO
====

.. py:module:: amaranth_soc.gpio

The :mod:`amaranth_soc.gpio` module provides a basic GPIO peripheral.

.. testsetup::

   from amaranth import *
   from amaranth.lib import io, wiring
   from amaranth.lib.wiring import In, Out, flipped, connect

   from amaranth_soc import csr, gpio


Introduction
------------

`GPIO <https://en.wikipedia.org/wiki/General-purpose_input/output>`_ peripherals are commonly used
to interface a SoC (usually a microcontroller) with a variety of external circuitry. This module contains a GPIO peripheral which can be connected to a :ref:`CSR bus<csr-bus-introduction>`.

Example
+++++++

This example shows a GPIO peripheral being used to drive four LEDs:

.. testcode::

   class MySoC(wiring.Component):
       def elaborate(self, platform):
           m = Module()

           m.submodules.led_gpio = led_gpio = gpio.Peripheral(pin_count=4, addr_width=8,
                                                              data_width=8)

           for n in range(4):
               led = io.Buffer("o", platform.request("led", n, dir="-"))
               connect(m, led_gpio.pins[n], led)

           m.submodules.csr_decoder = csr_decoder = csr.Decoder(addr_width=31, data_width=8)
           csr_decoder.add(led_gpio.bus, addr=0x1000, name="led_gpio")

           # ...

           return m

Pin modes
---------

.. autoclass:: PinMode()

Pin interface
-------------

.. autoclass:: PinSignature()

Peripheral
----------

.. autoclass:: amaranth_soc.gpio::Peripheral.Mode()
.. autoclass:: amaranth_soc.gpio::Peripheral.Input()
.. autoclass:: amaranth_soc.gpio::Peripheral.Output()
.. autoclass:: amaranth_soc.gpio::Peripheral.SetClr()

.. autoclass:: Peripheral()
   :no-members:
