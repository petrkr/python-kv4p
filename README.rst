python-kv4p
===========

Python implementation of the `KV4P-HT <https://github.com/VanceVagell/kv4p-ht>`_
radio protocol: KISS framing, the KV4P vendor envelope, and the ``Kv4pRadio``
orchestrator (HELLO handshake, flow control, PTT, device state tracking).

Targets the v2.0.0.1 Android/FW17 protocol line.

Full documentation: https://petrkr.github.io/python-kv4p/

Install
-------

.. code-block:: sh

    pip install python-kv4p

Usage
-----

.. code-block:: python

    from kv4p import Kv4pRadio
    from kv4p.transports.serial import Kv4pSerialTransport

    transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
    radio = Kv4pRadio(transport)
    radio.on_rx_audio(...)
    radio.on_sql(...)

    with radio:
        # radio.freq_rx / .bandwidth / .squelch / ... are seeded from the
        # firmware's actual tuned state, reported in HELLO right after connect().
        radio.set_frequency(145.500, 145.500)
        radio.set_tx_allowed(True)
        radio.set_ptt(True)
        radio.send_tx_audio(payload)
        radio.set_ptt(False)

``Kv4pRadio`` context manager calls ``connect()``/``disconnect()`` automatically.
``connect()`` hardware-resets the ESP32 over RTS/DTR and blocks until HELLO is
received, since the firmware only sends it once at boot — this is also how the
radio's settings properties get their initial values, straight from the
firmware's own DeviceState. Operations that need the handshake
(``set_frequency``, ``set_bandwidth``, ``set_squelch``, ``set_ctcss``,
``set_ptt``, ``send_tx_audio``, ...) raise ``RadioNotReadyError`` if called
before that.

For tests or hardware-free runs, use ``kv4p.transports.dummy.DummyTransport``,
which answers ``reset()`` with a synthetic HELLO.

Layout
------

.. code-block:: text

    kv4p/
      __init__.py       # Kv4pRadio, vendor encode/decode
      state_tracker.py  # DeviceStateTracker: handshake, device state, settings, PTT
      flow_control.py   # FlowControlWindow: HTTP/2-like flow control
      constants/        # numeric/bit constants (kiss, vendor, messages)
      protocol/         # wire framing: kiss.py
      messages/         # one file per KV4P payload (dataclasses)
      transports/       # Kv4pTransport interface, serial + dummy implementations
