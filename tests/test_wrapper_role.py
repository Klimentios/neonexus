"""The role is pasted into every wake prompt: it must come back as one short clean line."""
import io
import json
import unittest
from unittest import mock

import wrapper


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FetchRoleTests(unittest.TestCase):
    def _fetch(self, roles):
        body = json.dumps(roles).encode()
        with mock.patch('urllib.request.urlopen', return_value=_Resp(body)):
            return wrapper._fetch_role(8300, 'claude')

    def test_role_is_clamped_single_line_without_controls(self):
        role = 'Reviewer\x1b[201~\r\nrm -rf ~\x07' + 'x' * 200 + '\x9b'
        got = self._fetch({'claude': role})
        self.assertLessEqual(len(got), wrapper.ROLE_MAX_CHARS)
        self.assertTrue(got.startswith('Reviewer[201~ rm -rf ~x'))
        self.assertFalse(any(ord(c) < 0x20 or 0x7f <= ord(c) <= 0x9f for c in got))

    def test_plain_role_unchanged_and_non_string_dropped(self):
        self.assertEqual(self._fetch({'claude': 'Architect'}), 'Architect')
        self.assertEqual(self._fetch({'claude': {'x': 1}}), '')
        self.assertEqual(self._fetch({}), '')


if __name__ == '__main__':
    unittest.main()
