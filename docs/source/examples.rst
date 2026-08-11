Examples
========

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
