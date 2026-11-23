import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1] / "rootfs/usr"
APP = ROOT / "lib/home-tv"
ADDONS = ROOT / "share/kodi/addons"


class RetroUiTests(unittest.TestCase):
    def setUp(self):
        self.dialog = Mock()
        self.run = Mock()
        self.show_error = Mock()
        self.builtin = Mock()
        kodi = {
            "xbmc": SimpleNamespace(executebuiltin=self.builtin),
            "xbmcaddon": SimpleNamespace(Addon=Mock()),
            "xbmcgui": SimpleNamespace(Dialog=lambda: self.dialog, WindowXMLDialog=object,
                                       ALPHANUM_HIDE_INPUT=2),
            "xbmcplugin": SimpleNamespace(),
            "common": SimpleNamespace(run=self.run, russian=lambda: True, show_error=self.show_error,
                                       tr=lambda ru, en: ru, usb_drives=lambda: []),
            "setup": SimpleNamespace(audio_menu=Mock(), bluetooth_menu=Mock(), panel_url=Mock(),
                                     select_wifi=Mock(), set_pin=Mock()),
        }
        self.enterContext(patch.dict(sys.modules, kodi))
        self.enterContext(patch.object(sys, "path", [str(APP), str(ADDONS / "script.hometv"), *sys.path]))

    def test_native_games_section_contains_three_consoles(self):
        widget = runpy.run_path(str(ADDONS / "plugin.hometv.widgets/default.py"))
        tiles = list(widget["game_tiles"](False))
        self.assertEqual([tile[0] for tile in tiles], [
            "retrogames:nes", "retrogames:megadrive", "retrogames:psx",
        ])
        widget["run_action"]("retrogames:psx")
        widget["run_action"]("retrogames:../../test")
        self.builtin.assert_called_once_with("RunAddon(script.hometv,action=retrogames:psx)")

    def test_browsing_filters_files_and_follows_only_regular_directories(self):
        browse_roms = runpy.run_path(str(ADDONS / "script.hometv/roms.py"))["browse_roms"]
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "NES"
            folder = root / "Collection"
            folder.mkdir(parents=True)
            (folder / "Readme.txt").touch()
            (folder / ".hidden.nes").touch()
            game = folder / "Example.NES"
            game.touch()
            if sys.platform != "win32":
                outside = Path(temporary) / "outside.nes"
                outside.touch()
                (folder / "external.nes").symlink_to(outside)
            self.dialog.select.side_effect = [1, 1]
            self.assertEqual(browse_roms(self.dialog, "NES", root, (".nes",)), game.resolve())
            self.assertEqual(self.dialog.select.call_args_list[1].args[1], ["← Назад", "Example.NES"])

    def test_parental_group_gate_controls_rom_launch(self):
        import hometv_state

        with TemporaryDirectory() as temporary:
            config = Path(temporary)
            (config / "parental.json").write_text(json.dumps({"locked": ["games"]}), encoding="utf-8")
            (config / "pin.json").write_text(json.dumps(hometv_state.make_pin("123456")), encoding="utf-8")
            with patch.object(hometv_state, "CONFIG", config):
                launch = runpy.run_path(str(ADDONS / "script.hometv/default.py"))["launch"]
            rom = config / "Example.nes"
            chooser = Mock(return_value=rom)
            with patch.dict(launch.__globals__, {"select_rom": chooser}):
                self.dialog.input.side_effect = ["654321", "123456"]
                launch("retrogames:nes")
                chooser.assert_not_called()
                self.run.assert_not_called()
                launch("retrogames:nes")
                self.run.assert_called_once_with(
                    "/usr/lib/home-tv/session", "emulate", "nes", str(rom), timeout=18,
                )
