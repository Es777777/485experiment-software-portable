"""Tests for the email feedback module (scripts.email_feedback)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import email_feedback  # noqa: E402


class _FakeSMTP:
    def __init__(self) -> None:
        self.logged_in_with: tuple[str, str] | None = None
        self.sent_messages: list = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, sender, auth_code):
        self.logged_in_with = (sender, auth_code)

    def send_message(self, msg):
        self.sent_messages.append(msg)


class ConfigLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(self._temp_dir())

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @staticmethod
    def _temp_dir() -> str:
        import tempfile
        return tempfile.mkdtemp()

    def test_load_email_config_rejects_missing(self) -> None:
        with self.assertRaises(FileNotFoundError):
            email_feedback.load_email_config(self.tmpdir / "nope.json")

    def test_load_email_config_rejects_missing_sender(self) -> None:
        path = self.tmpdir / "email.json"
        path.write_text(json.dumps({"auth_code": "abc"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            email_feedback.load_email_config(path)

    def test_load_email_config_reads_full_payload(self) -> None:
        path = self.tmpdir / "email.json"
        path.write_text(
            json.dumps(
                {
                    "sender": "me@qq.com",
                    "auth_code": "xyz",
                    "smtp_host": "smtp.qq.com",
                    "smtp_port": 465,
                }
            ),
            encoding="utf-8",
        )
        cfg = email_feedback.load_email_config(path)
        self.assertEqual(cfg.sender, "me@qq.com")
        self.assertEqual(cfg.auth_code, "xyz")
        self.assertEqual(cfg.smtp_host, "smtp.qq.com")
        self.assertEqual(cfg.smtp_port, 465)

    def test_write_email_config_round_trip(self) -> None:
        path = self.tmpdir / "email.json"
        email_feedback.write_email_config(path, sender="me@qq.com", auth_code="abc")
        cfg = email_feedback.load_email_config(path)
        self.assertEqual(cfg.sender, "me@qq.com")
        self.assertEqual(cfg.auth_code, "abc")


class RateLimitDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_path = self.tmpdir / "state.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_first_send_is_allowed(self) -> None:
        decision = email_feedback.evaluate_rate_limit(self.state_path, now=1000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.sent_today, 0)

    def test_recent_send_blocks_until_cooldown(self) -> None:
        # Seed state by writing a recent send directly (no SMTP needed)
        from scripts import email_feedback as ef
        today = ef.time.strftime("%Y-%m-%d")
        self.state_path.write_text(
            json.dumps(
                {
                    "last_sent_at": 1000.0,
                    "sent_today": 1,
                    "today": today,
                }
            ),
            encoding="utf-8",
        )
        decision = email_feedback.evaluate_rate_limit(
            self.state_path, now=1010.0, min_interval=60.0, today=today
        )
        self.assertFalse(decision.allowed)
        self.assertGreater(decision.seconds_to_wait, 0.0)

    def test_daily_limit_blocks(self) -> None:
        # Use a no-op smtp so we can fast-forward the day
        for i in range(email_feedback.RATE_LIMIT_MAX_PER_DAY):
            decision = email_feedback.send_feedback(
                config=email_feedback.EmailConfig(sender="a@qq.com", auth_code="x"),
                subject="hi",
                body="x" * 12,
                sender_label="tester",
                state_path=self.state_path,
                smtp_login=lambda smtp: None,
                smtp_send=lambda smtp: None,
                now=2000.0 + i * 200.0,  # 200s apart, > 60s
            )
            self.assertTrue(decision.allowed, f"send #{i + 1} should be allowed")
        decision = email_feedback.evaluate_rate_limit(
            self.state_path, now=2000.0 + 21 * 200.0
        )
        self.assertFalse(decision.allowed)
        self.assertIn("上限", decision.reason)

    def test_new_day_resets_counter(self) -> None:
        # Saturate the limit using "now" timestamps so we control the clock
        from scripts import email_feedback as ef
        first_today = ef.time.strftime("%Y-%m-%d", ef.time.localtime(3000.0))
        next_today = ef.time.strftime("%Y-%m-%d", ef.time.localtime(3000.0 + 25 * 3600.0))
        for i in range(email_feedback.RATE_LIMIT_MAX_PER_DAY):
            email_feedback.send_feedback(
                config=email_feedback.EmailConfig(sender="a@qq.com", auth_code="x"),
                subject="hi",
                body="x" * 12,
                sender_label="tester",
                state_path=self.state_path,
                smtp_login=lambda smtp: None,
                smtp_send=lambda smtp: None,
                now=3000.0 + i * 200.0,
                today=first_today,
            )
        # Move to a different day (well past 24h) and verify counter resets
        decision = email_feedback.evaluate_rate_limit(
            self.state_path, now=3000.0 + 25 * 3600.0, today=next_today
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.sent_today, 0)


class SendFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_path = self.tmpdir / "state.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_send_uses_injected_smtp(self) -> None:
        fake = _FakeSMTP()
        decision = email_feedback.send_feedback(
            config=email_feedback.EmailConfig(sender="me@qq.com", auth_code="xyz"),
            subject="测试",
            body="这是测试反馈内容，描述问题。",
            sender_label="user@example.com",
            state_path=self.state_path,
            smtp_login=lambda smtp: fake.login("me@qq.com", "xyz"),
            smtp_send=lambda smtp: fake.send_message(object()),
            now=4000.0,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.sent_today, 1)
        self.assertEqual(fake.logged_in_with, ("me@qq.com", "xyz"))
        # Cooldown should now be in effect
        decision2 = email_feedback.evaluate_rate_limit(
            self.state_path, now=4000.0 + 5.0
        )
        self.assertFalse(decision2.allowed)

    def test_send_propagates_smtp_errors(self) -> None:
        def _boom(smtp):
            raise RuntimeError("auth failed")

        with self.assertRaises(RuntimeError):
            email_feedback.send_feedback(
                config=email_feedback.EmailConfig(sender="me@qq.com", auth_code="xyz"),
                subject="测试",
                body="这是测试反馈内容，描述问题。",
                sender_label="user",
                state_path=self.state_path,
                smtp_login=_boom,
                smtp_send=_boom,
                now=5000.0,
            )
        # state should not have advanced
        decision = email_feedback.evaluate_rate_limit(
            self.state_path, now=5000.0 + 5.0
        )
        self.assertTrue(decision.allowed)


class CooldownInfoTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_path = self.tmpdir / "state.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_initial_state_has_full_cooldown_used(self) -> None:
        cooldown, sent, limit = email_feedback.remaining_cooldown_seconds(
            self.state_path
        )
        self.assertEqual(sent, 0)
        self.assertEqual(limit, email_feedback.RATE_LIMIT_MAX_PER_DAY)
        self.assertEqual(cooldown, 0.0)
    def test_cooldown_decreases_with_time(self) -> None:
        from scripts import email_feedback as ef
        today = ef.time.strftime("%Y-%m-%d")
        email_feedback.send_feedback(
            config=email_feedback.EmailConfig(sender="a@qq.com", auth_code="x"),
            subject="hi",
            body="x" * 12,
            sender_label="tester",
            state_path=self.state_path,
            smtp_login=lambda smtp: None,
            smtp_send=lambda smtp: None,
            now=6000.0,
            today=today,
        )
        cooldown, sent, _ = email_feedback.remaining_cooldown_seconds(
            self.state_path, now=6000.0 + 30.0, today=today
        )
        self.assertAlmostEqual(cooldown, 30.0, delta=1.0)
        self.assertEqual(sent, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
