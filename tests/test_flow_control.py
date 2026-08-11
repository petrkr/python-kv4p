"""Tests for flow control window."""

from kv4p.flow_control import FlowControlWindow


class TestFlowControlWindow:
    """Unit tests for FlowControlWindow (HTTP/2-like flow control)."""

    def test_initial_size(self):
        """Test window starts at configured size."""
        window = FlowControlWindow(2048)
        assert window._size == 2048

    def test_reset(self):
        """Test resetting window size."""
        window = FlowControlWindow(100)
        assert window._size == 100

        window.reset(2000)
        assert window._size == 2000

    def test_claim_success(self):
        """Test claiming space within window."""
        window = FlowControlWindow(2048)
        assert window.claim(100, timeout=0.1) is True
        assert window._size == 1948

    def test_claim_exact_size(self):
        """Test claiming exactly the window size."""
        window = FlowControlWindow(100)
        assert window.claim(100, timeout=0.1) is True
        assert window._size == 0

    def test_claim_exceeds_window_timeout(self):
        """Test claiming more than available times out."""
        window = FlowControlWindow(100)
        assert window.claim(101, timeout=0.05) is False
        assert window._size == 100  # unchanged

    def test_claim_multiple(self):
        """Test multiple claims."""
        window = FlowControlWindow(1000)
        assert window.claim(300, timeout=0.1) is True
        assert window.claim(400, timeout=0.1) is True
        assert window.claim(300, timeout=0.1) is True
        assert window._size == 0

    def test_claim_multiple_overflow(self):
        """Test claim times out when window exhausted."""
        window = FlowControlWindow(1000)
        assert window.claim(600, timeout=0.1) is True
        assert window.claim(400, timeout=0.1) is True
        assert window.claim(1, timeout=0.05) is False  # should timeout
        assert window._size == 0

    def test_add_refills_window(self):
        """Test adding to window (WINDOW_UPDATE)."""
        window = FlowControlWindow(1000)
        assert window.claim(800, timeout=0.1) is True
        assert window._size == 200

        window.add(500)
        assert window._size == 700

    def test_reset_clears_state(self):
        """Test reset changes window size."""
        window = FlowControlWindow(1000)
        assert window.claim(900, timeout=0.1) is True
        assert window._size == 100

        window.reset(2000)
        assert window._size == 2000

    def test_zero_window_timeout(self):
        """Test behavior with zero window size."""
        window = FlowControlWindow(0)
        assert window.claim(1, timeout=0.05) is False
        assert window._size == 0

    def test_large_window(self):
        """Test with large window."""
        window = FlowControlWindow(1000000)
        assert window.claim(999999, timeout=0.1) is True
        assert window._size == 1
        assert window.claim(1, timeout=0.1) is True
        assert window._size == 0
