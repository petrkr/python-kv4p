python-kv4p
===========

Python implementation of the `KV4P-HT <https://github.com/VanceVagell/kv4p-ht>`_
radio protocol: KISS framing, the KV4P vendor envelope, and the ``Kv4pRadio``
orchestrator (HELLO handshake, flow control, PTT, device state tracking).

Targets the v2.0.0.1 Android/FW17 protocol line.

Install
-------

.. code-block:: sh

    pip install python-kv4p

Usage
-----

.. code-block:: python

    from kv4p import Kv4pRadio, Kv4pSettings
    from kv4p.transports.serial import Kv4pSerialTransport

    transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
    radio = Kv4pRadio(transport, on_rx_audio=..., on_sql=...)

    with radio:
        radio.configure(Kv4pSettings(rx_freq=145.500, tx_freq=145.500, tx_allowed=True))
        radio.set_ptt(True)
        radio.send_tx_audio(payload)
        radio.set_ptt(False)

``Kv4pRadio.open()``/``reset()`` hardware-reset the ESP32 over RTS/DTR and
block until HELLO is received, since the firmware only sends it once, at
boot. Operations that need the handshake (``configure``, ``set_frequency``,
``set_ptt``, ``send_tx_audio``) raise ``RadioNotReadyError`` if called before
that.

For tests or hardware-free runs, use ``kv4p.transports.dummy.DummyTransport``,
which answers ``reset()`` with a synthetic HELLO.

Layout
------

.. code-block:: text

    kv4p/
      __init__.py        # Kv4pRadio, Kv4pSettings, vendor encode/decode
      settings.py         # Kv4pSettings
      state_tracker.py      # DeviceStateTracker: handshake, device state, HostDesiredState, PTT
      flow_control.py         # FlowControlWindow: HTTP/2-like flow control
      logging_utils.py          # Throttle / ChangeGate
      constants/                  # numeric/bit constants (kiss, vendor, messages)
      protocol/                    # wire framing: kiss.py, ax25.py
      messages/                     # one file per KV4P payload (dataclasses)
      transports/                    # Kv4pTransport interface, serial + dummy implementations
