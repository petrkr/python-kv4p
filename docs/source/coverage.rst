Test Coverage
==============

The latest CI run's reports are published alongside this documentation:

- `Test report <tests/report.html>`_
- `Coverage report <tests/coverage/index.html>`_

Run tests with coverage report locally:

.. code-block:: sh

    python -m pytest tests/ -v --cov=kv4p --cov-report=html
