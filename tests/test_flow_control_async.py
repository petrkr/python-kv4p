"""Async/threading tests for flow control window."""

import threading
import time

from kv4p.flow_control import FlowControlWindow


class TestFlowControlAsync:
    """Tests for concurrent access and WINDOW_UPDATE notifications."""

    def test_claim_blocks_until_space_available(self):
        """Test that claim() blocks until space becomes available via add()."""
        window = FlowControlWindow(500)
        claim_result = []

        # Thread that tries to claim 1000 bytes (more than available)
        def claimer():
            result = window.claim(1000, timeout=2.0)
            claim_result.append(result)

        thread = threading.Thread(target=claimer)
        thread.start()

        # Give thread time to start claiming
        time.sleep(0.2)

        # After 0.5s, add the missing bytes
        time.sleep(0.3)
        window.add(500)

        # Thread should succeed now
        thread.join(timeout=3.0)
        assert len(claim_result) == 1
        assert claim_result[0] is True
        assert window._size == 0

    def test_claim_timeout_without_add(self):
        """Test that claim() times out if add() never happens."""
        window = FlowControlWindow(100)

        # Try to claim 1000 bytes with short timeout
        result = window.claim(1000, timeout=0.2)

        assert result is False
        assert window._size == 100  # unchanged

    def test_multiple_claimers_waiting(self):
        """Test multiple threads waiting for space."""
        window = FlowControlWindow(200)
        results = []
        lock = threading.Lock()

        def claimer(size):
            result = window.claim(size, timeout=2.0)
            with lock:
                results.append((size, result))

        # Start two threads trying to claim 150 each (total 300, but only 200 available)
        t1 = threading.Thread(target=claimer, args=(150,))
        t2 = threading.Thread(target=claimer, args=(150,))

        t1.start()
        time.sleep(0.1)
        t2.start()

        # First claim should succeed (150 < 200)
        t1.join(timeout=1.0)

        # Second claim still waiting (only 50 left, needs 150)
        time.sleep(0.1)

        # Add enough for second claim
        window.add(100)

        t2.join(timeout=1.0)

        assert len(results) == 2
        assert results[0] == (150, True)
        assert results[1] == (150, True)
        assert window._size == 0

    def test_add_wakes_all_waiters(self):
        """Test that add() wakes all waiting threads."""
        window = FlowControlWindow(0)  # Empty window
        results = []
        lock = threading.Lock()

        def claimer():
            result = window.claim(100, timeout=2.0)
            with lock:
                results.append(result)

        # Start 3 threads all waiting
        threads = [threading.Thread(target=claimer) for _ in range(3)]
        for t in threads:
            t.start()

        time.sleep(0.2)

        # Add space for all
        window.add(300)

        for t in threads:
            t.join(timeout=1.0)

        assert len(results) == 3
        assert all(r is True for r in results)
        assert window._size == 0

    def test_claim_partial_then_complete(self):
        """Test claiming in stages as space becomes available."""
        window = FlowControlWindow(200)
        results = []

        # First claim: succeeds
        assert window.claim(200, timeout=0.1) is True
        results.append(True)

        # Second claim: needs to wait for more space
        def delayed_claim():
            result = window.claim(300, timeout=2.0)
            results.append(result)

        thread = threading.Thread(target=delayed_claim)
        thread.start()

        time.sleep(0.2)

        # Add first batch
        window.add(200)
        time.sleep(0.1)

        # Add second batch to complete the claim
        window.add(100)

        thread.join(timeout=3.0)

        assert len(results) == 2
        assert all(r is True for r in results)
        assert window._size == 0
