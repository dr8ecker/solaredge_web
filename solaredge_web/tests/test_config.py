import json
import tempfile
import unittest
from pathlib import Path

import yaml

from app.config import Config, ConfigurationError


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "options.json"

    def load(self, values):
        self.path.write_text(json.dumps(values), encoding="utf-8")
        return Config.load(self.path, data_dir=Path(self.directory.name))

    def test_supervisor_example_and_python_defaults_agree(self):
        root = Path(__file__).resolve().parents[1]
        manifest = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
        example = json.loads((root / "examples/options.normal.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["options"], example)
        self.assertEqual(set(manifest["options"]), set(manifest["schema"]))
        config = self.load(manifest["options"])
        for name, value in manifest["options"].items():
            self.assertEqual(getattr(Config(), name), value)
        self.assertEqual(config.storage_state_path.parent, Path(self.directory.name))

    def test_bad_options_do_not_echo_values(self):
        for values in ({"poll_interval": True}, {"page_timeout": 1}, {"mode": "invalid"},
                       {"unknown": "secret"}, {"mqtt_port": 65536}):
            with self.subTest(values=values), self.assertRaises(ConfigurationError) as caught:
                self.load(values)
            self.assertNotIn("secret", str(caught.exception))

    def test_credentials_are_not_in_dataclass_repr(self):
        config = self.load({"solar_edge_username": "private@example.com",
                            "solar_edge_password": "private-pass"})
        self.assertNotIn("private", repr(config))

    def test_rejects_credentials_and_tokens_in_configured_urls(self):
        for url in ("https://user:pass@example.com/", "https://example.com/?token=secret",
                    "https://example.com/#secret", "http://example.com/", "file:///tmp/example"):
            with self.subTest(url=url), self.assertRaises(ConfigurationError):
                self.load({"monitoring_url": url})

    def test_handles_missing_invalid_and_nonobject_config(self):
        with self.assertRaises(ConfigurationError):
            Config.load(self.path)
        for text in ("{", "[]", '"not an object"'):
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                Config.load(self.path)
