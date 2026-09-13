import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'install_service', Path(__file__).parent / 'scripts/install-service.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root = base / 'checkout'
        (self.root / 'dist/client').mkdir(parents=True)
        (self.root / 'dist/client/index.html').write_text('built')
        self.template = self.root / 'kernel-inbox.service'
        self.original = Path(__file__).with_name('kernel-inbox.service').read_text()
        self.template.write_text(self.original)
        self.config = base / 'config'
        self.destination = self.config / 'systemd/user/kernel-inbox.service'
        self.destination.parent.mkdir(parents=True)
        self.backup = self.destination.with_suffix('.service.bak')
        for mocked in (
            patch.object(installer, 'ROOT', self.root),
            patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.config)}),
            patch.object(installer.sys, 'argv', ['install-service.py']),
            patch.object(installer.sys, 'platform', 'linux'),
            patch.object(installer.shutil, 'which', return_value='/usr/bin/systemctl'),
            patch('sys.stdout', new_callable=io.StringIO),
            patch('sys.stderr', new_callable=io.StringIO),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)
        run = patch.object(installer.subprocess, 'run')
        self.run = run.start()
        self.addCleanup(run.stop)

    def assert_installed(self):
        self.assertFalse(self.destination.is_symlink())
        self.assertEqual(self.destination.read_text(), installer.render())
        self.assertNotIn('@PROJECT_DIR@', self.destination.read_text())
        self.assertNotIn('@PYTHON@', self.destination.read_text())
        self.assertEqual(self.template.read_text(), self.original)
        self.run.assert_any_call(
            ['systemctl', '--user', 'enable', '--now', 'kernel-inbox.service'], check=True)

    def test_fresh_install(self):
        installer.main()
        self.assert_installed()
        self.assertFalse(self.backup.exists())

    def test_template_symlink_is_preserved_without_overwriting_source(self):
        self.destination.symlink_to(self.template)
        installer.main()
        self.assert_installed()
        self.assertTrue(self.backup.is_symlink())
        self.assertEqual(self.backup.readlink(), self.template)

    def test_dangling_service_symlink_is_replaced_without_creating_target(self):
        missing = self.root / 'missing.service'
        self.destination.symlink_to(missing)
        installer.main()
        self.assert_installed()
        self.assertEqual(self.backup.readlink(), missing)
        self.assertFalse(missing.exists())

    def test_regular_service_is_backed_up(self):
        self.destination.write_text('previous service')
        installer.main()
        self.assert_installed()
        self.assertEqual(self.backup.read_text(), 'previous service')

    def test_existing_backup_file_or_symlink_blocks_install(self):
        self.destination.symlink_to(self.template)
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    self.backup.symlink_to(self.root / 'missing-backup')
                else:
                    self.backup.write_text('keep backup')
                with self.assertRaises(SystemExit):
                    installer.main()
                self.assertEqual(self.destination.readlink(), self.template)
                self.assertEqual(self.template.read_text(), self.original)
                self.assertTrue(self.backup.is_symlink() if symlink else
                                self.backup.read_text() == 'keep backup')
                self.run.assert_not_called()
                self.backup.unlink()
