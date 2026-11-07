"""Exercise real child-process timeouts without hanging a real tmux server."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

import wrapper_unix


@unittest.skipIf(sys.platform == 'win32', 'Unix executable fixture')
class InjectTimeoutTests(unittest.TestCase):
    def test_stuck_delivery_and_cleanup_return_without_retyping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = root / 'calls'
            executable = root / 'tmux'
            executable.write_text(
                '#!' + sys.executable + '\n'
                'import os, sys, time\n'
                'verb = sys.argv[1]\n'
                'with open(os.environ["TEST_TMUX_CALLS"], "a") as f: f.write(verb + "\\n")\n'
                'if verb == os.environ["TEST_TMUX_STALL"]: time.sleep(30)\n'
                'if verb == "display-message": print("%7")\n'
                'if verb == "paste-buffer" and os.environ["TEST_TMUX_STALL"] == "delete-buffer": sys.exit(1)\n'
            )
            executable.chmod(0o755)
            for stalled in ['display-message', 'load-buffer', 'paste-buffer', 'send-keys', 'delete-buffer']:
                with self.subTest(stalled=stalled):
                    calls.write_text('')
                    env = {'PATH': str(root) + os.pathsep + os.environ.get('PATH', ''),
                           'TEST_TMUX_CALLS': str(calls), 'TEST_TMUX_STALL': stalled}
                    with mock.patch.dict(os.environ, env), mock.patch.object(wrapper_unix, 'TMUX_COMMAND_TIMEOUT', .2):
                        start = time.monotonic()
                        ok = wrapper_unix.inject('short test', tmux_session='test', delay=0)
                        elapsed = time.monotonic() - start
                    verbs = calls.read_text().splitlines()
                    self.assertIs(ok, False)
                    self.assertLess(elapsed, 3, 'a child-process hang must be bounded')
                    self.assertLessEqual(verbs.count('paste-buffer'), 1, 'do not retry a possibly delivered paste')
                    self.assertLessEqual(verbs.count('send-keys'), 1, 'do not repeat Enter')
                    if stalled != 'send-keys':
                        self.assertNotIn('send-keys', verbs, 'no Enter after an earlier failure')


class InjectSanitizeTests(unittest.TestCase):
    def test_strips_escape_c0_c1_and_flattens_newlines(self):
        raw = 'role\x1b[201~rm -rf ~\r\nnext\x07\x00\x7f\x85\x9b1;2H\tend é ✓'
        clean = wrapper_unix.sanitize_inject_text(raw)
        self.assertEqual(clean, 'role[201~rm -rf ~  next1;2H\tend é ✓')
        for ch in clean:
            code = ord(ch)
            self.assertFalse(code < 0x20 and ch != '\t', repr(ch))
            self.assertFalse(0x7f <= code <= 0x9f, repr(ch))

    def test_inject_loads_sanitized_text_into_tmux(self):
        seen = []

        def fake_run(args, **kwargs):
            seen.append((args, kwargs.get('input')))
            out = b'%1\n' if args[1] == 'display-message' else b''
            return mock.Mock(returncode=0, stdout=out, stderr=b'')

        with mock.patch.object(wrapper_unix.subprocess, 'run', side_effect=fake_run), \
                mock.patch.object(wrapper_unix.time, 'sleep'):
            ok = wrapper_unix.inject('hi\x1b[201~\x03there\nok', tmux_session='s', delay=0)
        self.assertTrue(ok)
        loaded = [inp for args, inp in seen if args[1] == 'load-buffer']
        self.assertEqual(loaded, [b'hi[201~there ok'])
