import ast
import contextlib
import io
import json
import subprocess
import sys
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from notebook_helpers import NOTEBOOK


class SetupTests(unittest.TestCase):
    def setUp(self):
        notebook = json.loads(NOTEBOOK.read_text())
        source = ''.join(notebook['cells'][2]['source'])
        tree = ast.parse(source)
        tree.body = [node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
        self.namespace = {}
        exec(compile(tree, str(NOTEBOOK), 'exec'), self.namespace)

    def test_successful_setup_is_quiet(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.namespace['run_setup']([sys.executable, '-c',
                                        'print("install chatter")'])
        self.assertEqual(output.getvalue(), '')

    def test_failed_setup_shows_stdout_stderr_and_raises(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(subprocess.CalledProcessError):
                self.namespace['run_setup']([sys.executable, '-c',
                    'import sys; print("context"); print("failure", file=sys.stderr); sys.exit(2)'])
        self.assertIn('context', output.getvalue())
        self.assertIn('failure', output.getvalue())

    def test_optional_failure_still_shows_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.namespace['run_setup']([sys.executable, '-c',
                'print("cleanup failed"); raise SystemExit(1)'], check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('cleanup failed', output.getvalue())

    def test_internet_tries_second_service(self):
        with patch('urllib.request.urlopen', side_effect=[
            urllib.error.URLError('unreachable'), MagicMock()]) as request:
            self.namespace['check_internet']()
        self.assertEqual(request.call_count, 2)

    def test_no_internet_has_actionable_error_and_cause(self):
        error = urllib.error.URLError('unreachable')
        with patch('urllib.request.urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'Settings panel and enable Internet') as caught:
                self.namespace['check_internet']()
        self.assertIs(caught.exception.__cause__, error)

    def test_http_error_confirms_connection(self):
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(
                'https://pypi.org', 503, 'Unavailable', {}, None)):
            self.namespace['check_internet']()
