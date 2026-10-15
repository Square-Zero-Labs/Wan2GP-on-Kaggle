"""Real Wan2GP decodes; opt in with WAN2GP_SOURCE and FFMPEG_TEST_BINARIES."""
import contextlib
import importlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from notebook_helpers import compatibility_cell


@unittest.skipUnless(os.environ.get('WAN2GP_SOURCE'), 'set WAN2GP_SOURCE to a Wan2GP checkout')
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.upstream = Path(os.environ['WAN2GP_SOURCE'])
        cls.generator = shutil.which('ffmpeg')
        cls.ffprobe = shutil.which('ffprobe')
        cls.binaries = [str(Path(p).resolve()) for p in os.environ.get(
            'FFMPEG_TEST_BINARIES', cls.generator).split(os.pathsep)]
        cls.frames = np.arange(24 * 24 * 32 * 3, dtype=np.uint8).reshape(24, 24, 32, 3)
        # Give every frame a distinct identity, preserved by lossless RGB encoding.
        cls.frames[:, :, :, 0] = np.arange(24, dtype=np.uint8)[:, None, None] * 9
        cls.cfr = cls.root / 'constant rate.mp4'
        cls.vfr = cls.root / 'variable rate.mp4'
        cls.offset = cls.root / 'offset.mp4'
        cls.sar = cls.root / 'anamorphic.mp4'
        for path, filters in [
            (cls.cfr, []),
            (cls.offset, ['-vf', 'setpts=PTS+2/TB']),
            (cls.sar, ['-vf', 'setsar=2']),
        ]:
            subprocess.run([
                cls.generator, '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgb24',
                '-video_size', '32x24', '-framerate', '12', '-i', 'pipe:0',
                *filters, '-vsync', '0', '-c:v', 'libx264rgb', '-crf', '0', '-preset', 'ultrafast', str(path),
            ], input=cls.frames.tobytes(), check=True, capture_output=True)
        # Genuine irregular timestamps rather than simply a lower constant rate.
        subprocess.run([
            cls.generator, '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgb24',
            '-video_size', '32x24', '-framerate', '12', '-i', 'pipe:0',
            '-vf', "select='eq(n,0)+eq(n,1)+eq(n,4)+eq(n,10)+eq(n,11)+eq(n,20)'",
            '-vsync', '0', '-c:v', 'libx264rgb', '-crf', '0',
            '-preset', 'ultrafast', '-y', str(cls.vfr),
        ], input=cls.frames.tobytes(), check=True, capture_output=True)
        cls.original_source = (cls.upstream / 'shared/utils/video_decode.py').read_text()

    @contextlib.contextmanager
    def decoder(self, binary, configure=True):
        repo = self.root / 'repo'
        utils = repo / 'shared/utils'
        utils.mkdir(parents=True, exist_ok=True)
        target = utils / 'video_decode.py'
        target.write_text(self.original_source)
        shutil.copy2(self.upstream / 'shared/utils/virtual_media.py', utils / 'virtual_media.py')
        package_name = '_wan2gp_media_test'
        package = types.ModuleType(package_name)
        package.__path__ = [str(utils)]
        sys.modules[package_name] = package
        with patch.dict(os.environ, {'FFMPEG_BINARY': binary, 'FFPROBE_BINARY': self.ffprobe}):
            if configure:
                # Execute the complete notebook cell, including the setup call.
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compatibility_cell(), {'WAN2GP_ROOT': repo})
            try:
                module = importlib.import_module(package_name + '.video_decode')
                yield module
            finally:
                for name in list(sys.modules):
                    if name == package_name or name.startswith(package_name + '.'):
                        del sys.modules[name]

    def for_each_binary(self):
        for binary in self.binaries:
            version = subprocess.run([binary, '-version'], check=True, capture_output=True,
                                     text=True).stdout.splitlines()[0]
            print('\nMedia test:', version)
            yield binary

    def test_original_error_reproduces_on_legacy_and_modern_source_is_unchanged(self):
        for binary in self.for_each_binary():
            with self.subTest(binary=binary):
                help_text = subprocess.run([binary, '-h', 'full'], check=True,
                                           capture_output=True, text=True).stdout
                with self.decoder(binary, configure=False) as decoder:
                    if '-fps_mode' not in help_text:
                        with self.assertRaisesRegex(RuntimeError, "Unrecognized option.*fps_mode"):
                            decoder.decode_video_frames_ffmpeg(str(self.cfr), 0, 24, bridge='numpy')
                    else:
                        actual = decoder.decode_video_frames_ffmpeg(str(self.cfr), 0, 24, bridge='numpy')
                        self.np.testing.assert_array_equal(actual, self.frames)
                with self.decoder(binary):
                    changed = (self.root / 'repo/shared/utils/video_decode.py').read_text()
                    if '-fps_mode' in help_text:
                        self.assertEqual(changed, self.original_source)
                    else:
                        self.assertEqual(changed, self.original_source.replace(
                            'cmd += ["-fps_mode", "passthrough", "-frames:v",',
                            'cmd += ["-vsync", "0", "-frames:v",'))

    def test_contiguous_seek_and_frame_limit(self):
        for binary in self.for_each_binary():
            with self.subTest(binary=binary), self.decoder(binary) as decoder:
                for start, count in [(0, 24), (5, 7), (20, 99), (24, 3)]:
                    actual = decoder.decode_video_frames_ffmpeg(str(self.cfr), start, count, bridge='numpy')
                    self.np.testing.assert_array_equal(actual, self.frames[start:start + count])

    def test_sparse_selection_order_duplicates_and_resampling(self):
        for binary in self.for_each_binary():
            with self.subTest(binary=binary), self.decoder(binary) as decoder:
                indices = [23, 0, 11, 0]  # Span forces the separate sparse-select command.
                actual = decoder.decode_video_frame_indices_ffmpeg(str(self.cfr), indices, bridge='numpy')
                self.np.testing.assert_array_equal(actual, self.frames[indices])
                actual = decoder.decode_video_frames_ffmpeg(str(self.cfr), 0, 6, target_fps=6, bridge='numpy')
                self.np.testing.assert_array_equal(actual, self.frames[[0, 2, 4, 6, 8, 10]])

    def test_variable_timestamps_do_not_duplicate_or_drop_frames(self):
        for binary in self.for_each_binary():
            with self.subTest(binary=binary), self.decoder(binary) as decoder:
                actual = decoder.decode_video_frames_ffmpeg(str(self.vfr), 0, 24, bridge='numpy')
                self.np.testing.assert_array_equal(actual, self.frames[[0, 1, 4, 10, 11, 20]])

    def test_offset_timestamps_from_start_and_virtual_clip(self):
        for binary in self.for_each_binary():
            with self.subTest(binary=binary), self.decoder(binary) as decoder:
                actual = decoder.decode_video_frames_ffmpeg(str(self.offset), 0, 24, bridge='numpy')
                self.np.testing.assert_array_equal(actual, self.frames)
                virtual_path = str(self.cfr) + '|start_frame=5,end_frame=14'
                actual = decoder.decode_video_frames_ffmpeg(virtual_path, 2, 4, bridge='numpy')
                self.np.testing.assert_array_equal(actual, self.frames[7:11])

    def test_passthrough_preserves_timestamp_and_frame_hashes(self):
        def hashes(binary, mode):
            result = subprocess.run([
                binary, '-v', 'error', '-copyts', '-i', str(self.vfr),
                *mode, '-pix_fmt', 'rgb24', '-f', 'framemd5', 'pipe:1',
            ], check=True, capture_output=True, text=True)
            # Packet durations vary across encoder versions; rawvideo consumers
            # use frame identity/order and timestamps, which must agree.
            rows = [line.split(',') for line in result.stdout.splitlines()
                    if line and not line.startswith('#')]
            return [tuple(parts[i].strip() for i in (0, 1, 2, 4, 5)) for parts in rows]

        expected = hashes(self.generator, ['-vsync', '0'])
        self.assertEqual(len(expected), 6)
        pts = [int(row[2]) for row in expected]
        self.assertEqual(pts, [0, 1, 4, 10, 11, 20])
        for binary in self.for_each_binary():
            with self.subTest(binary=binary):
                self.assertEqual(hashes(binary, ['-vsync', '0']), expected)
                help_text = subprocess.run([binary, '-h', 'full'], check=True,
                                           capture_output=True, text=True).stdout
                if '-fps_mode' in help_text:
                    self.assertEqual(hashes(binary, ['-fps_mode', 'passthrough']), expected)

    def test_pixel_aspect_correction_matches_modern_decode(self):
        with self.decoder(self.generator) as decoder:
            expected = decoder.decode_video_frames_ffmpeg(str(self.sar), 0, 24, bridge='numpy')
        self.assertEqual(expected.shape, (24, 24, 64, 3))
        for binary in self.for_each_binary():
            with self.subTest(binary=binary), self.decoder(binary) as decoder:
                actual = decoder.decode_video_frames_ffmpeg(str(self.sar), 0, 24, bridge='numpy')
                # Different libswscale versions may round interpolation by one unit.
                self.assertEqual(actual.shape, expected.shape)
                self.assertLessEqual(int(self.np.abs(actual.astype(int) - expected).max()), 1)


if __name__ == '__main__':
    unittest.main()
