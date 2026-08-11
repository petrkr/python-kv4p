Examples
========

All scripts under ``examples/`` accept a ``--device`` argument for the
serial port, defaulting to ``/dev/ttyUSB0``:

.. code-block:: sh

    python examples/basic_info.py --device /dev/ttyUSB5

Basic Connection and Info
--------------------------

Connect to a radio on serial port and display firmware version and current settings:

.. code-block:: python

    from kv4p import Kv4pRadio
    from kv4p.transports.serial import Kv4pSerialTransport

    transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
    radio = Kv4pRadio(transport)

    with radio:
        hello = radio.hello
        print(f"Firmware: {hello.version.ver}")
        print(f"RX Frequency: {radio.freq_rx:.3f} MHz")
        print(f"TX Frequency: {radio.freq_tx:.3f} MHz")
        print(f"Bandwidth: {radio.bandwidth}")

See ``examples/basic_info.py`` for the complete example.

Device State and Events
------------------------

Register callbacks for squelch, physical PTT and periodic device state updates:

.. code-block:: python

    from kv4p import Kv4pRadio
    from kv4p.transports.serial import Kv4pSerialTransport

    transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
    radio = Kv4pRadio(transport)

    radio.on_sql(lambda open_: print(f"SQL {'open' if open_ else 'closed'}"))
    radio.on_phy_ptt(lambda down: print(f"PHY PTT {'down' if down else 'up'}"))

    with radio:
        radio.set_rx_audio_open(True)
        ...

Squelch, physical PTT and TX active state are also readable directly without
a callback, via ``radio.sql_open``, ``radio.phy_ptt`` and ``radio.tx_active``.

See ``examples/with_events.py`` and ``examples/device_state_monitor.py`` for
complete examples.

Transmitting a WAV File
-------------------------

Encode a 48 kHz mono 16-bit WAV file to Opus and transmit it. Requires the
``opuslib`` package (not a python-kv4p dependency):

.. code-block:: sh

    pip install opuslib
    python examples/send_audio_file.py my_audio.wav --device /dev/ttyUSB0

See ``examples/send_audio_file.py`` for the complete example.

Testing Without Hardware
--------------------------

Use ``DummyTransport`` for testing without a radio connected:

.. code-block:: python

    from kv4p import Kv4pRadio
    from kv4p.transports.dummy import DummyTransport

    transport = DummyTransport()
    radio = Kv4pRadio(transport)

    with radio:
        print(f"Firmware: {radio.hello.version.ver}")
