"""Installed free games and the persistent home of each game."""

import os


def puzzle(game_id, name_ru, name_en):
    return {
        'name_ru': name_ru,
        'name_en': name_en,
        'icon': f'/usr/share/icons/hicolor/96x96/apps/sgt-{game_id}.png',
        'binary': f'/usr/games/sgt-{game_id}',
        'toolkit': 'gtk',
    }


GAMES = {
    'solo': puzzle('solo', 'Судоку', 'Solo (Sudoku)'),
    'fifteen': puzzle('fifteen', 'Пятнашки', 'Fifteen'),
    'bridges': puzzle('bridges', 'Мосты', 'Bridges'),
    'lightup': puzzle('lightup', 'Лампочки', 'Light Up'),
    'mines': puzzle('mines', 'Сапёр', 'Mines'),
    'lbreakouthd': {
        'name_ru': 'LBreakoutHD',
        'name_en': 'LBreakoutHD',
        'icon': '/usr/share/icons/hicolor/256x256/apps/lbreakouthd.png',
        'binary': '/usr/games/lbreakouthd',
        'toolkit': 'sdl',
    },
}


def game_session(game_id, home):
    game = GAMES.get(game_id)
    if game is None:
        raise ValueError('Неизвестная игра')
    directory = home / '.local/share/home-tv/games' / game_id
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = os.environ | {
        'HOME': str(directory),
        'XDG_CONFIG_HOME': str(directory / 'config'),
        'XDG_DATA_HOME': str(directory / 'data'),
        'XDG_STATE_HOME': str(directory / 'state'),
        'XDG_CACHE_HOME': str(directory / 'cache'),
    }
    command = ['/usr/bin/cage', '--']
    if game['toolkit'] == 'gtk':
        environment['GDK_BACKEND'] = 'wayland'
    else:
        # Debian's SDL executable is setgid games. Without group elevation it
        # uses its personal highscores file under the game home directory.
        environment['SDL_VIDEODRIVER'] = 'wayland'
        command.extend(('/usr/bin/setpriv', '--no-new-privs', '--'))
    return [*command, game['binary']], environment, directory
