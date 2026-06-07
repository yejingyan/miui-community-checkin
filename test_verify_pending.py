#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import verify_pending

class VerifyPendingTests(unittest.TestCase):
    def test_save_and_load_pending_url(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'pending.json'
            verify_pending.PENDING_FILE = path
            verify_pending.save_pending('https://example.com/check.html?x=1', source='test')
            data = json.loads(path.read_text())
            self.assertEqual(data['url'], 'https://example.com/check.html?x=1')
            self.assertEqual(data['source'], 'test')
            self.assertIn('created_at', data)
            self.assertEqual(verify_pending.load_pending()['url'], 'https://example.com/check.html?x=1')

    def test_clear_pending(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'pending.json'
            verify_pending.PENDING_FILE = path
            verify_pending.save_pending('https://example.com/check.html')
            verify_pending.clear_pending()
            self.assertFalse(path.exists())

if __name__ == '__main__':
    unittest.main()
