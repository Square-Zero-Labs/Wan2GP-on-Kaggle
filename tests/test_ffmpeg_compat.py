import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from notebook_helpers import NOTEBOOK, compatibility_cell, load_configure


COMMAND = '    cmd += ["-fps_mode", "passthrough", "-frames:v", "3", "-f", "rawvideo", "pipe:1"]\n'
SOURCE = 'def contiguous(cmd):\n' + COMMAND + '\ndef sparse(cmd):\n' + COMMAND
LEGACY = SOURCE.replace('"-fps_mode", "passthrough"', '"-vsync", "0"')


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'shared/utils/video_decode.py'
        self.target.parent.mkdir(parents=True)
        self.target.write_text(SOURCE)
        self.configure = load_configure()

    def run_configure(self, help_text='-vsync sync_method', override='', bundled=False):
        if override:
            Path(override).touch()
        if bundled:
            binary = self.root / 'ffmpeg_bins/ffmpeg'
            binary.parent.mkdir(exist_ok=True)
            binary.touch()
        results = [subprocess.CompletedProcess([], 0, 'ffmpeg version test\n', ''),
                   subprocess.CompletedProcess([], 0, help_text, '')]
        with patch.dict(os.environ, {'FFMPEG_BINARY': override}), \
             patch('shutil.which', return_value='/system/ffmpeg'), \
             patch('subprocess.run', side_effect=results) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            self.configure(self.root)
        return run

    def test_legacy_patches_both_decoders_and_is_idempotent(self):
        other = self.root / 'unrelated.py'
        other.write_text('mode = "-fps_mode cfr"\n')
        self.run_configure()
        self.assertEqual(self.target.read_text(), LEGACY)
        modified = self.target.stat().st_mtime_ns
        self.run_configure()
        self.assertEqual(self.target.stat().st_mtime_ns, modified)
        self.assertEqual(other.read_text(), 'mode = "-fps_mode cfr"\n')

    def test_modern_leaves_source_and_mtime_unchanged(self):
        modified = self.target.stat().st_mtime_ns
        self.run_configure('-fps_mode[:stream_specifier] mode\n-vsync sync_method')
        self.assertEqual(self.target.read_text(), SOURCE)
        self.assertEqual(self.target.stat().st_mtime_ns, modified)

    def test_resolves_override_then_bundle_then_path(self):
        override = str(self.root / 'custom-ffmpeg')
        run = self.run_configure(override=override, bundled=True)
        self.assertEqual(run.call_args_list[0].args[0][0], override)
        run = self.run_configure(bundled=True)
        self.assertEqual(run.call_args_list[0].args[0][0], str(self.root / 'ffmpeg_bins/ffmpeg'))
        (self.root / 'ffmpeg_bins/ffmpeg').unlink()
        run = self.run_configure()
        self.assertEqual(run.call_args_list[0].args[0][0], '/system/ffmpeg')

    def test_unknown_upstream_command_fails_without_partial_write(self):
        source = SOURCE + '\nother = ["-fps_mode", "cfr"]\n'
        self.target.write_text(source)
        with self.assertRaisesRegex(RuntimeError, 'commands have changed'):
            self.run_configure()
        self.assertEqual(self.target.read_text(), source)

    def test_neither_option_fails_without_write(self):
        with self.assertRaisesRegex(RuntimeError, 'neither'):
            self.run_configure('other options')
        self.assertEqual(self.target.read_text(), SOURCE)

    def test_probe_error_is_not_treated_as_legacy(self):
        with patch('shutil.which', return_value='/system/ffmpeg'), \
             patch.dict(os.environ, {'FFMPEG_BINARY': ''}), \
             patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'ffmpeg')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.configure(self.root)
        self.assertEqual(self.target.read_text(), SOURCE)

    def test_missing_binary_has_actionable_error(self):
        with patch('shutil.which', return_value=None), \
             patch.dict(os.environ, {'FFMPEG_BINARY': ''}):
            with self.assertRaisesRegex(RuntimeError, 'Rerun Step 4'):
                self.configure(self.root)

    def test_older_or_already_fixed_upstream_does_not_need_patch(self):
        self.target.write_text('cmd = ["ffmpeg", "-vsync", "0"]\n')
        self.run_configure()
        self.target.unlink()
        self.run_configure()

    def test_notebook_cell_runs_before_launch_and_is_valid_python(self):
        notebook = json.loads(NOTEBOOK.read_text())
        sources = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
        for source in sources:
            compile(source, str(NOTEBOOK), 'exec')
        compat = sources.index(compatibility_cell())
        self.assertLess(next(i for i, s in enumerate(sources) if "'apt-get', 'install'" in s), compat)
        self.assertLess(compat, next(i for i, s in enumerate(sources) if 'subprocess.Popen(' in s))


if __name__ == '__main__':
    unittest.main()
