import unittest, tempfile, os
from unittest.mock import patch
from docagent.config import Settings


class ConfigTests(unittest.TestCase):
    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            Settings(timeout=-1)

    def test_invalid_steps(self):
        with self.assertRaises(ValueError):
            Settings(max_steps=7)
