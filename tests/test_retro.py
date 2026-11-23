import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_streaming import load_program

import hometv_retro as retro


class RetroGamesTests(unittest.TestCase):
    def test_unicode_path_keeps_spaces_and_colons_across_session_socket(self):
        session = load_program('session')
        path = '/media/hometv/Флешка/Денди: игра.nes'
        args = ['emulate', 'nes', path]
        self.assertEqual(session.selection_from_command(args), f'retro:nes:{path}')
        left, right = socket.socketpair()
        with left, right, patch.object(session, 'switch') as switch:
            left.sendall((json.dumps(args, ensure_ascii=False) + '\n').encode())
            session.handle_connection(right)
            switch.assert_called_once_with(args)

    def test_console_and_extension_must_match(self):
        for console, name in (('other', '/media/hometv/example.nes'),
                              ('nes', 'example.nes'), ('nes', '/media/hometv/example.cue'),
                              ('psx', '/media/hometv/disk\n.chd')):
            with self.subTest(console=console, name=name), self.assertRaises(ValueError):
                retro.selection_for_rom(console, name)

    def test_playstation_playlist_validates_tracks_and_blocks_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            discs = parent / 'PlayStation'
            discs.mkdir()
            track = discs / 'Диск 1.bin'
            track.write_bytes(b'test placeholder')
            cue = discs / 'Диск 1.cue'
            cue.write_text('FILE "Диск 1.bin" BINARY\n  TRACK 01 MODE2/2352\n', encoding='utf-8-sig')
            playlist = discs / 'Игра.m3u'
            playlist.write_text('# PlayStation\nДиск 1.cue\n', encoding='utf-8')
            retro.validate_discs(playlist)
            track.rename(parent / track.name)
            cue.write_text('FILE "../Диск 1.bin" BINARY\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                retro.validate_discs(playlist)
            cue.write_text('FILE "Отсутствует.bin" BINARY\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'отсутствует файл'):
                retro.validate_discs(playlist)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'RetroArch profile uses the Linux filesystem')
    def test_session_uses_its_core_and_keeps_settings_on_next_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            path = home / 'roms/nes/Денди (тест).nes'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'fixture')
            cores = home / 'cores'
            cores.mkdir()
            core = cores / 'nestopia_libretro.so'
            core.touch()
            with patch.object(retro, 'CORES', cores):
                args, _, directory = retro.retro_session('nes', str(path), home)
                self.assertEqual(args, ['/usr/bin/cage', '--', '/usr/bin/retroarch', '--config',
                                        str(directory / 'retroarch.cfg'), '-L', str(core), '--', str(path)])
                self.assertIn('input_joypad_driver = "udev"', (directory / 'retroarch.cfg').read_text())
                (directory / 'retroarch.cfg').write_text('user setting')
                retro.retro_session('nes', str(path), home)
            self.assertEqual((directory / 'retroarch.cfg').read_text(), 'user setting')
            self.assertTrue((directory / 'saves').is_dir())
            self.assertTrue((home / 'bios/nes').is_dir())
