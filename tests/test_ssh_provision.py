from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


if sys.platform != "linux":
    raise unittest.SkipTest("SSH provisioning requires Linux file permissions and locking")

RUNTIME = Path(__file__).resolve().parents[1] / "rootfs/usr/lib/home-tv"
sys.path.insert(0, str(RUNTIME))
LOADER = SourceFileLoader("hometv_admin", str(RUNTIME / "admin"))
admin = module_from_spec(spec_from_loader(LOADER.name, LOADER))
LOADER.exec_module(admin)


class SSHProvisionTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        self.patch_paths = patch.multiple(
            admin, AUTHORIZED_KEYS=root / "tvadmin", SSH_ENABLED=root / "enabled",
            SSH_ADMIN=root / "admin", SSH_PROVISION=root / "hometv-ssh.pub",
        )
        self.patch_paths.start()
        self.addCleanup(self.patch_paths.stop)
        command = patch.object(admin, "command")
        self.command = command.start()
        self.addCleanup(command.stop)

    def test_default_and_invalid_key_leave_ssh_disabled(self):
        admin.provision_ssh()
        self.assertFalse(admin.SSH_ENABLED.exists())
        admin.SSH_PROVISION.write_text("command=\"/bin/sh\" ssh-ed25519 Zm9v", encoding="utf-8")
        with self.assertRaises(ValueError):
            admin.provision_ssh()
        self.assertFalse(admin.SSH_ENABLED.exists())
        self.assertFalse(admin.AUTHORIZED_KEYS.exists())

    def test_boot_key_can_enable_ssh_but_panel_cannot_replace_it(self):
        admin.SSH_PROVISION.write_text("ssh-ed25519 Zm9v operator\n", encoding="utf-8-sig")
        admin.provision_ssh()
        self.assertEqual(admin.ssh_status({}), {"enabled": True, "admin": True})
        self.command.assert_called_once()
        self.assertEqual(admin.AUTHORIZED_KEYS.read_bytes(), b"ssh-ed25519 Zm9v operator\n")
        with self.assertRaises(ValueError):
            admin.ssh_configure({"enabled": True, "key": "ssh-ed25519 YmFy"})
        admin.ssh_configure({"enabled": False})
        admin.provision_ssh()
        self.assertFalse(admin.SSH_ENABLED.exists())
        admin.SSH_PROVISION.write_text("ssh-ed25519 YmFy operator\n", encoding="utf-8")
        admin.provision_ssh()
        self.assertEqual(admin.AUTHORIZED_KEYS.read_bytes(), b"ssh-ed25519 YmFy operator\n")
        self.assertTrue(admin.SSH_ENABLED.exists())
