import json
import logging
import tempfile
import time
import unittest
from pathlib import Path

from app.config import Config
from app.health import HealthManager, healthy
from app.logging_config import SafeFormatter
from app.main import retry_delay


class HealthLoggingTests(unittest.TestCase):
    def test_masks_known_secrets_email_and_url_query(self):
        formatter = SafeFormatter(("sensitive-pass", "token-value"))
        record = logging.LogRecord("test", logging.ERROR, "", 0,
                                   "sensitive-pass token-value user@example.com https://example.com/?code=private", (), None)
        result = formatter.format(record)
        for secret in ("sensitive-pass", "token-value", "user@example.com", "code=private"):
            self.assertNotIn(secret, result)
        self.assertEqual(json.loads(result)["level"], "ERROR")

    def test_health_tolerates_one_failure_then_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HealthManager(Config(mode='smoke_test', data_dir=Path(directory)))
            moment = time.time()
            manager.update(status="page_loaded", browser_connected=True, last_page_success=moment)
            self.assertTrue(healthy(manager.path, now=moment + 1))
            manager.update(status="error", consecutive_failures=1)
            self.assertTrue(healthy(manager.path, now=moment + 1))
            manager.update(heartbeat_at=moment)
            self.assertFalse(healthy(manager.path, now=moment + 2000))

    def test_health_rejects_dead_browser_and_stopped_process(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HealthManager(Config(mode='smoke_test', data_dir=Path(directory)))
            manager.update(last_page_success=time.time(), browser_connected=False)
            self.assertFalse(healthy(manager.path))
            manager.update(status="offline")
            self.assertFalse(healthy(manager.path))

    def test_health_accepts_startup_grace_but_not_forever(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HealthManager(Config(mode='smoke_test', data_dir=Path(directory)))
            manager.update()
            self.assertTrue(healthy(manager.path))
            manager.update(started_at=time.time() - 301)
            self.assertFalse(healthy(manager.path))

    def test_backoff_is_bounded(self):
        self.assertEqual([retry_delay(n) for n in range(1, 6)], [10, 30, 60, 120, 300])
        self.assertEqual(retry_delay(100), 300)
