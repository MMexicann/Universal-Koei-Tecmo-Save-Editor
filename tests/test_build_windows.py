"""Windows build input filtering; all filesystem fixtures are synthetic."""
from importlib.metadata import version
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

            with patch.object(sys, 'path', [str(site_packages), *sys.path]):
                with with_numpy_metadata_only(site_packages):
                    self.assertFalse(provenance.exists())
                    self.assertFalse(record.exists())
                    self.assertEqual(metadata.read_bytes(), b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
                    self.assertEqual(list(metadata_dir.iterdir()), [metadata])
                    self.assertEqual(version('numpy'), '2.5.4')

            self.assertEqual(provenance.read_bytes(), b'synthetic runner build paths')
            self.assertEqual(record.read_bytes(), b'synthetic wheel inventory')
            self.assertEqual(notice.read_bytes(), b'reviewed package notice')

    def test_numpy_distribution_metadata_is_restored_when_build_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            site_packages = Path(temporary)
            metadata_dir = site_packages / 'numpy-2.5.4.dist-info'
            metadata_dir.mkdir()
            metadata = metadata_dir / 'METADATA'
            metadata.write_bytes(b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
            provenance = metadata_dir / 'DELVEWHEEL'
            provenance.write_bytes(b'synthetic runner build paths')

            with self.assertRaisesRegex(RuntimeError, 'synthetic build failure'):
                with with_numpy_metadata_only(site_packages):
                    self.assertFalse(provenance.exists())
                    raise RuntimeError('synthetic build failure')

            self.assertEqual(metadata.read_bytes(), b'Metadata-Version: 2.4\nName: numpy\nVersion: 2.5.4\n')
            self.assertEqual(provenance.read_bytes(), b'synthetic runner build paths')

    def test_missing_numpy_version_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            site_packages = Path(temporary)
            (site_packages / 'numpy-2.5.4.dist-info').mkdir()
            with self.assertRaisesRegex(RuntimeError, 'NumPy version metadata is missing'):
                with with_numpy_metadata_only(site_packages):
                    pass


if __name__ == '__main__':
    unittest.main()
