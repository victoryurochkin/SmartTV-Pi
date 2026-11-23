import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch


ROOTFS = Path(__file__).resolve().parents[1] / 'rootfs'
APP = ROOTFS / 'usr/lib/home-tv'
sys.path.insert(0, str(APP))

from hometv_games import GAMES, game_session
from hometv_streaming import validate_catalogue


def load_program(name):
    loader = importlib.machinery.SourceFileLoader(f'test_hometv_{name}', str(APP / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.service = {'id': 'youtube-tv', 'name': 'YouTube', 'url': 'https://www.youtube.com/tv'}

    def test_catalogue_and_package_defaults(self):
        packaged = ROOTFS / 'usr/share/home-tv/services.json'
        services = validate_catalogue(json.loads(packaged.read_text(encoding='utf-8')))
        self.assertGreaterEqual(len(services), 16)
        self.assertTrue(services['youtube-tv']['prefer_h264'])
        self.assertTrue(all(not service.get('user_agent') for service in services.values()))

    def test_invalid_urls_identifiers_flags_and_zoom_are_rejected(self):
        for bad_values in (
            {'id': '../system'}, {'id': '-foo'}, {'id': 'Новый'},
            {'url': 'file:///etc/passwd'}, {'url': 'http://example.org'},
            {'url': 'https://local:54321@example.org'}, {'url': 'https://example.org:0'},
            {'flags': ['--no-sandbox']}, {'flags': [{'autoplay': True}]},
            {'user_agent': 'agent\nnew line'}, {'zoom': True}, {'zoom': float('nan')},
        ):
            with self.subTest(bad_values=bad_values), self.assertRaises(ValueError):
                validate_catalogue({'services': [self.service | bad_values]})
        with self.assertRaises(ValueError):
            validate_catalogue({'services': [self.service, self.service]})

    def test_browser_runs_in_cage_with_safe_profile_options(self):
        browser = load_program('browser')
        service = self.service | {'prefer_h264': True, 'flags': ['autoplay'], 'zoom': 1.1}
        args = browser.browser_command(
            service, PurePosixPath('/data/test profile'), PurePosixPath('/run/test'), 2
        )
        self.assertEqual(args[:3], ['/usr/bin/cage', '--', '/usr/bin/chromium'])
        self.assertIn('--user-data-dir=/data/test profile', args)
        self.assertIn('--renderer-process-limit=2', args)
        self.assertIn('--force-device-scale-factor=1.1', args)
        self.assertIn('--autoplay-policy=no-user-gesture-required', args)
        self.assertTrue(any('youtube-h264' in arg for arg in args))
        self.assertNotIn('--no-sandbox', args)
        self.assertNotIn('--disable-component-update', args)
        self.assertEqual(args[-1], self.service['url'])

    def test_session_recovery_and_strict_request_parsing(self):
        session = load_program('session')
        with self.assertRaises(ValueError):
            session.switch(['open', '../../ssh.service'])
        with tempfile.TemporaryDirectory() as directory:
            selection = Path(directory) / 'service-id'
            failure = subprocess.CalledProcessError(1, ['systemctl', 'start', session.BROWSER])
            with patch.object(session, 'SELECTION', selection), patch.object(
                session.subprocess, 'run', return_value=subprocess.CompletedProcess([], 3)
            ), patch.object(session, 'start_unit', side_effect=(failure, None)) as start:
                with self.assertRaises(subprocess.CalledProcessError):
                    session.switch(['open', 'youtube-tv'])
            self.assertEqual(selection.read_text(encoding='ascii'), 'youtube-tv\n')
            self.assertEqual([call.args[0] for call in start.call_args_list], [session.BROWSER, session.KODI])

    def test_native_games_use_installed_binaries_and_separate_profiles(self):
        session = load_program('session')
        required = {'solo', 'fifteen', 'bridges', 'lightup', 'mines'}
        self.assertTrue(required <= GAMES.keys())
        self.assertEqual(session.selection_from_command(['open', 'youtube-tv']), 'youtube-tv')
        for bad_command in (['game', '../browser'], ['game', 'netflix'], ['open', 'game:solo'],
                            ['game', 'solo', '--anything']):
            with self.subTest(bad_command=bad_command), self.assertRaises(ValueError):
                session.selection_from_command(bad_command)

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for game_id in required:
                self.assertEqual(session.selection_from_command(['game', game_id]), f'game:{game_id}')
                command, environment, game_home = game_session(game_id, home)
                self.assertEqual(command, ['/usr/bin/cage', '--', f'/usr/games/sgt-{game_id}'])
                self.assertTrue(game_home.is_dir())
                self.assertEqual(game_home, home / '.local/share/home-tv/games' / game_id)
                self.assertEqual(environment['HOME'], str(game_home))
                self.assertEqual(environment['XDG_CONFIG_HOME'], str(game_home / 'config'))
                self.assertEqual(environment['GDK_BACKEND'], 'wayland')
            command, environment, game_home = game_session('lbreakouthd', home)
            self.assertEqual(command, ['/usr/bin/cage', '--', '/usr/bin/setpriv', '--no-new-privs',
                                       '--', '/usr/games/lbreakouthd'])
            self.assertEqual(environment['HOME'], str(game_home))
            self.assertEqual(environment['SDL_VIDEODRIVER'], 'wayland')

    def test_browser_unit_excludes_kodi_and_has_exit_recovery(self):
        source = (ROOTFS / 'etc/systemd/system/home-tv-browser.service').read_text(encoding='utf-8')
        self.assertIn('Conflicts=home-tv-kodi.service', source)
        self.assertIn('home-tv-profile.service home-tv-kodi.service', source)
        self.assertIn('OnFailure=home-tv-browser-recover.service', source)


if __name__ == '__main__':
    unittest.main()
