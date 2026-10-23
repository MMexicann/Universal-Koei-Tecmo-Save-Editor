"""Windows build input filtering; all filesystem fixtures are synthetic."""
import importlib.util
from importlib.metadata import distribution, version
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.build_windows import with_numpy_metadata_only


class WindowsBuildTests(unittest.TestCase):
    def test_only_numpy_version_metadata_is_visible_during_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            site_packages = Path(temporary)
            metadata_dir = site_packages / 'numpy-2.5.4.dist-info'
            metadata_dir.mkdir()
            metadata = metadata_dir / 'METADATA'
            metadata.write_bytes(b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
            provenance = metadata_dir / 'DELVEWHEEL'
            provenance.write_bytes(b'synthetic runner build paths')
            record = metadata_dir / 'RECORD'
            record.write_bytes(b'synthetic wheel inventory')
            notice_dir = metadata_dir / 'licenses'
            notice_dir.mkdir()
            notice = notice_dir / 'LICENSE.txt'
            notice.write_bytes(b'reviewed package notice')

            original_sys_path = list(sys.path)
            with patch.object(sys, 'path', [str(site_packages), *sys.path]):
                before_context_sys_path = list(sys.path)
                with with_numpy_metadata_only(site_packages) as staging_root:
                    staged_metadata_dir = staging_root / metadata_dir.name
                    self.assertEqual(tuple(path.name for path in staged_metadata_dir.iterdir()),
                                     ('METADATA',))
                    self.assertEqual((staged_metadata_dir / 'METADATA').read_bytes(), metadata.read_bytes())
                    self.assertEqual(metadata.read_bytes(), b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
                    self.assertTrue(provenance.is_file())
                    self.assertTrue(record.is_file())
                    self.assertTrue(notice.is_file())
                    self.assertEqual(Path(distribution('numpy')._path), staged_metadata_dir)
                    self.assertEqual(version('numpy'), '2.5.4')
                    numpy_spec = importlib.util.find_spec('numpy')
                    self.assertIsNotNone(numpy_spec)
                    self.assertNotEqual(Path(numpy_spec.origin).resolve().parent, staging_root)
                    self.assertEqual(sys.path[0], str(staging_root))

                self.assertEqual(sys.path, before_context_sys_path)
                self.assertFalse(staging_root.exists())
                self.assertEqual(provenance.read_bytes(), b'synthetic runner build paths')
                self.assertEqual(record.read_bytes(), b'synthetic wheel inventory')
                self.assertEqual(notice.read_bytes(), b'reviewed package notice')
            self.assertEqual(sys.path, original_sys_path)

    def test_installed_numpy_metadata_remains_intact_when_build_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            site_packages = Path(temporary)
            metadata_dir = site_packages / 'numpy-2.5.4.dist-info'
            metadata_dir.mkdir()
            metadata = metadata_dir / 'METADATA'
            metadata.write_bytes(b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
            provenance = metadata_dir / 'DELVEWHEEL'
            provenance.write_bytes(b'synthetic runner build paths')
            original_sys_path = list(sys.path)

            with self.assertRaisesRegex(RuntimeError, 'synthetic build failure'):
                with with_numpy_metadata_only(site_packages) as staging_root:
                    self.assertTrue(provenance.exists())
                    self.assertTrue((staging_root / metadata_dir.name / 'METADATA').is_file())
                    raise RuntimeError('synthetic build failure')

            self.assertEqual(metadata.read_bytes(), b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
            self.assertEqual(provenance.read_bytes(), b'synthetic runner build paths')
            self.assertEqual(sys.path, original_sys_path)

    def test_missing_numpy_version_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            site_packages = Path(temporary)
            (site_packages / 'numpy-2.5.4.dist-info').mkdir()
            with self.assertRaisesRegex(RuntimeError, 'NumPy version metadata is missing'):
                with with_numpy_metadata_only(site_packages):
                    pass


if __name__ == '__main__':
    unittest.main()
