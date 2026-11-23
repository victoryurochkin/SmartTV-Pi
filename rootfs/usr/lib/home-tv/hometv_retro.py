"""Console catalogue and RetroArch sessions for local game images."""

import os
from pathlib import Path
import re

from hometv_state import write_atomic


HOME = Path('/data/home')
CORES = Path('/usr/lib/home-tv/cores')
AUTOCONFIG = Path('/usr/share/home-tv/retroarch/autoconfig')
USB_BASES = (Path('/media/hometv'), Path('/run/media/hometv'))
CUE_FILE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+\S+\s*$', re.IGNORECASE)
CONSOLES = {
    'nes': {
        'name_ru': 'Денди / NES', 'name_en': 'Dendy / NES',
        'core': 'nestopia', 'extensions': ('.nes', '.unf', '.unif', '.fds'),
    },
    'megadrive': {
        'name_ru': 'Sega Mega Drive', 'name_en': 'Sega Mega Drive',
        'core': 'genesis_plus_gx', 'extensions': ('.md', '.gen', '.bin', '.smd'),
    },
    'psx': {
        'name_ru': 'PlayStation 1', 'name_en': 'PlayStation 1',
        'core': 'pcsx_rearmed', 'extensions': ('.cue', '.chd', '.pbp', '.m3u', '.iso'),
    },
}


def rom_roots(console_id, usb_devices):
    if console_id not in CONSOLES:
        raise ValueError('Неизвестная консоль')
    local = HOME / 'roms' / console_id
    local.mkdir(mode=0o700, parents=True, exist_ok=True)
    return [('Внутреннее хранилище', local),
            *((entry['label'], Path(entry['path'])) for entry in usb_devices)]


def selection_for_rom(console_id, path):
    console = CONSOLES.get(console_id)
    if console is None or not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Выберите игру для указанной консоли')
    if len(path.encode('utf-8')) >= 4096 or any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError('Недопустимое имя файла игры')
    rom = Path(path)
    if rom.suffix.lower() not in console['extensions']:
        raise ValueError('Этот формат не поддерживается выбранной консолью')
    return f'retro:{console_id}:{path}'


def retroarch_config(config, directory, bios):
    if config.exists():
        return
    settings = {
        'video_driver': 'gl',
        'video_context_driver': 'wayland',
        'video_fullscreen': 'true',
        'video_smooth': 'false',
        'audio_driver': 'pulse',
        'input_driver': 'wayland',
        'input_joypad_driver': 'udev',
        'input_autodetect_enable': 'true',
        'input_exit_emulator': 'f12',
        'input_menu_toggle': 'f1',
        'quit_press_twice': 'false',
        'input_menu_toggle_gamepad_combo': '7',
        'input_quit_gamepad_combo': '4',
        'input_player1_b': 'z',
        'input_player1_a': 'x',
        'input_player1_y': 'a',
        'input_player1_x': 's',
        'input_player1_select': 'rshift',
        'input_player1_start': 'enter',
        'joypad_autoconfig_dir': str(AUTOCONFIG),
        'libretro_directory': str(CORES),
        'libretro_info_path': '/usr/share/libretro/info',
        'core_info_cache_enable': 'false',
        'system_directory': str(bios),
        'savefile_directory': str(directory / 'saves'),
        'savestate_directory': str(directory / 'states'),
        'autosave_interval': '5',
        'menu_driver': 'rgui',
        'config_save_on_exit': 'true',
        'desktop_menu_enable': 'false',
        'menu_show_online_updater': 'false',
        'menu_show_core_updater': 'false',
        'load_dummy_on_core_shutdown': 'false',
    }
    payload = ''.join(f'{key} = "{value}"\n' for key, value in settings.items())
    write_atomic(config, payload.encode('utf-8'))


def disc_lines(path):
    with path.open('rb') as stream:
        data = stream.read(131073)
    if len(data) > 131072:
        raise ValueError('Список дорожек или дисков слишком большой')
    return data.decode('utf-8-sig').splitlines()


def relative_disc_file(source, name):
    relative = Path(name)
    if relative.is_absolute() or '\\' in name:
        raise ValueError('Используйте относительные пути к файлам диска')
    try:
        target = (source.parent / relative).resolve(strict=True)
    except FileNotFoundError as error:
        raise ValueError(f'Рядом с {source.name} отсутствует файл {relative.name}') from error
    if not target.is_relative_to(source.parent) or not target.is_file():
        raise ValueError('Файлы диска должны находиться в каталоге списка или его подпапках')
    return target


def validate_cue(path):
    tracks = 0
    for line in disc_lines(path):
        if not line.lstrip().upper().startswith(('FILE ', 'FILE\t')):
            continue
        match = CUE_FILE.fullmatch(line)
        if match is None:
            raise ValueError('Некорректная строка FILE в CUE')
        relative_disc_file(path, next(group for group in match.groups() if group is not None))
        tracks += 1
    if not tracks:
        raise ValueError('В CUE нет записей FILE')


def validate_discs(rom):
    if rom.suffix.lower() == '.cue':
        validate_cue(rom)
    elif rom.suffix.lower() == '.m3u':
        discs = [line for raw in disc_lines(rom) if (line := raw.strip()) and not line.startswith('#')]
        if not 1 <= len(discs) <= 64:
            raise ValueError('В M3U должно быть от 1 до 64 записей дисков')
        for name in discs:
            disc = relative_disc_file(rom, name)
            if disc.suffix.lower() not in ('.cue', '.chd', '.pbp', '.iso'):
                raise ValueError('M3U должен ссылаться на образы дисков PlayStation')
            if disc.suffix.lower() == '.cue':
                validate_cue(disc)


def retro_session(console_id, path, home):
    selection_for_rom(console_id, path)
    rom = Path(path).resolve(strict=True)
    local = home.resolve() / 'roms' / console_id
    if not any(rom.is_relative_to(directory) for directory in (local, *USB_BASES)) or not rom.is_file():
        raise ValueError('Откройте файл игры с USB или из каталога этой консоли')
    if console_id == 'psx':
        validate_discs(rom)

    core = CORES / f'{CONSOLES[console_id]["core"]}_libretro.so'
    if not core.is_file():
        raise ValueError('Ядро эмулятора не установлено')

    directory = home / '.local/share/home-tv/retroarch' / console_id
    bios = home / 'bios' / console_id
    for subdirectory in (bios, directory / 'saves', directory / 'states'):
        subdirectory.mkdir(mode=0o700, parents=True, exist_ok=True)
    config = directory / 'retroarch.cfg'
    retroarch_config(config, directory, bios)
    return ['/usr/bin/cage', '--', '/usr/bin/retroarch', '--config', str(config),
            '-L', str(core), '--', str(rom)], os.environ.copy(), directory
