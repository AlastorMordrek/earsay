from __future__ import annotations

import pytest
from earsay.text_manager import TextManager
from earsay.models import SubscriptionRequest


class TestTextManager:
    def test_append_and_all_text(self):
        tm = TextManager()
        tm.append("hello ")
        tm.append("world")
        assert tm.all_text() == "hello world"

    def test_checkpoint_basic(self):
        tm = TextManager()
        tm.append("hello world")
        cp = tm.set_checkpoint(5)
        assert cp.index == 0
        assert cp.position == 5
        assert cp.text == "hello"

    def test_checkpoint_clamps_to_length(self):
        tm = TextManager()
        tm.append("hi")
        cp = tm.set_checkpoint(100)
        assert cp.position == 2
        assert cp.text == "hi"

    def test_checkpoint_cannot_be_before_previous(self):
        tm = TextManager()
        tm.append("hello world")
        tm.set_checkpoint(5)
        with pytest.raises(ValueError, match="must be after"):
            tm.set_checkpoint(3)

    def test_checkpoint_cannot_be_empty(self):
        tm = TextManager()
        tm.append("hello")
        with pytest.raises(ValueError, match="must be positive"):
            tm.set_checkpoint(0)

    def test_new_text_returns_text_since_last_checkpoint(self):
        tm = TextManager()
        tm.append("hello world")
        assert tm.new_text().text == "hello world"
        assert tm.new_text().potential_index == 0

        tm.set_checkpoint(5)
        assert tm.new_text().text == " world"
        assert tm.new_text().potential_index == 1

    def test_re_checkpoint_can_expand(self):
        tm = TextManager()
        tm.append("hello world")
        tm.set_checkpoint(5)
        cp = tm.re_checkpoint(8)
        assert cp.position == 8
        assert cp.text == "hello wo"

    def test_re_checkpoint_can_shrink(self):
        tm = TextManager()
        tm.append("hello world")
        tm.set_checkpoint(5)
        cp = tm.re_checkpoint(3)
        assert cp.position == 3
        assert cp.text == "hel"

    def test_re_checkpoint_cannot_move_behind_previous(self):
        tm = TextManager()
        tm.append("hello beautiful world")
        tm.set_checkpoint(5)
        tm.set_checkpoint(15)
        with pytest.raises(ValueError, match="must be after"):
            tm.re_checkpoint(3)

    def test_re_checkpoint_no_checkpoints(self):
        tm = TextManager()
        tm.append("hello")
        with pytest.raises(ValueError, match="No checkpoints"):
            tm.re_checkpoint(3)

    def test_subscription_add_and_remove(self):
        tm = TextManager()
        req = SubscriptionRequest(chars=5, timeout_ms=1000)
        sub = tm.add_subscription(req)
        assert sub.ticket == req.ticket
        assert tm.subscription_count() == 1

        assert tm.remove_subscription(sub.ticket)
        assert tm.subscription_count() == 0

    def test_subscription_remove_nonexistent(self):
        tm = TextManager()
        assert not tm.remove_subscription("nonexistent")

    def test_status(self):
        tm = TextManager()
        tm.append("hello")
        s = tm.status
        assert s["chars_transcribed"] == 5
        assert s["checkpoint_count"] == 0
        assert s["subscription_count"] == 0
        assert "uptime_seconds" in s

    def test_multiple_checkpoints(self):
        tm = TextManager()
        tm.append("0123456789")
        cp0 = tm.set_checkpoint(3)
        cp1 = tm.set_checkpoint(7)
        assert cp0.index == 0
        assert cp0.text == "012"
        assert cp1.index == 1
        assert cp1.text == "3456"

    def test_new_text_with_three_checkpoints(self):
        tm = TextManager()
        tm.append("0123456789ABCDEF")
        tm.set_checkpoint(4)
        tm.set_checkpoint(8)
        tm.set_checkpoint(12)
        nt = tm.new_text()
        assert nt.text == "CDEF"
        assert nt.potential_index == 3
