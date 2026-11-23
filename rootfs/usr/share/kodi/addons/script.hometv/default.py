import os
from pathlib import Path
import subprocess
import sys

import xbmc
import xbmcaddon
import xbmcgui

from common import run, russian, show_error, tr, usb_drives
from hometv_games import GAMES
from hometv_retro import CONSOLES
from hometv_state import CONFIG, check_pin, read_json
from hometv_streaming import load_catalogue
from roms import select_rom
from setup import audio_menu, bluetooth_menu, panel_url, select_wifi, set_pin


ADDON = xbmcaddon.Addon()
DIALOG = xbmcgui.Dialog()
MEDIA_EXTENSIONS = {
    ".aac", ".aiff", ".ass", ".avi", ".bmp", ".cue", ".flac", ".gif", ".iso", ".jpeg",
    ".jpg", ".m2ts", ".m3u", ".m3u8", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4",
    ".mpeg", ".mpg", ".ogg", ".opus", ".png", ".ts", ".vob", ".wav", ".webm", ".webp", ".wmv",
}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def browse_usb(drive):
    root = Path(drive["path"]).resolve(strict=True)
    current = root
    while True:
        with os.scandir(current) as entries:
            children = [entry for entry in entries if not entry.name.startswith(".")
                        and not entry.is_symlink() and (entry.is_dir() or
                        Path(entry.name).suffix.lower() in MEDIA_EXTENSIONS)]
        children.sort(key=lambda item: (not item.is_dir(), item.name.casefold()))
        labels = [("▸ " if item.is_dir() else "") + item.name for item in children]
        choice = DIALOG.select(current.name, ["← " + tr("Назад", "Back"), *labels])
        if choice < 1:
            if current == root:
                return
            current = current.parent
            continue
        item = Path(children[choice - 1].path).resolve(strict=True)
        if not item.is_relative_to(root):
            continue
        if item.is_dir():
            current = item
        elif item.suffix.lower() in IMAGE_EXTENSIONS:
            from json import dumps
            xbmc.executeJSONRPC(dumps({"jsonrpc": "2.0", "id": 1, "method": "Player.Open",
                                      "params": {"item": {"file": str(item)}}}))
            return
        else:
            xbmc.Player().play(str(item))
            return


def choose_usb(eject=False):
    try:
        drives = usb_drives()
        if not drives:
            DIALOG.ok("USB", tr("Подключите накопитель к USB.", "Connect a USB drive."))
            return
        title = tr("Безопасное извлечение", "Safe removal") if eject else "USB"
        choice = DIALOG.select(title, [drive["label"] for drive in drives])
        if choice < 0:
            return
        drive = drives[choice]
        if eject:
            run("/usr/lib/home-tv/usb", "eject", drive["device"])
            DIALOG.notification("USB", tr("Накопитель можно извлечь", "Drive can be removed"))
        else:
            browse_usb(drive)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        xbmc.log(f"HomeTV USB: {type(exc).__name__}", xbmc.LOGWARNING)
        show_error(tr("Проверьте накопитель и завершите воспроизведение перед извлечением.",
                      "Check the drive and stop playback before removal."))


def device_settings():
    options = [tr("Настройки Kodi: экран и звук", "Kodi settings: display and audio"), "Wi-Fi",
               "Bluetooth", tr("Аудиовыход браузера", "Browser audio output"),
               tr("Задать или изменить PIN", "Set or change PIN")]
    choice = DIALOG.select(tr("Настройки HomeTV Pi", "HomeTV Pi settings"), options)
    if choice == 0:
        xbmc.executebuiltin("ActivateWindow(Settings)")
    elif choice >= 1:
        [select_wifi, bluetooth_menu, audio_menu, set_pin][choice - 1]()


def unlocked(action):
    try:
        locked = (read_json(CONFIG / "parental.json", {}) or {}).get("locked", [])
        gate = action.removeprefix("web:").removeprefix("retrogames:").replace("game:", "game-", 1)
        game_locked = action.startswith(("game:", "retrogames:")) and "games" in locked
        retro_locked = action.startswith("retrogames:") and "retrogames" in locked
        if gate not in locked and not game_locked and not retro_locked:
            return True
        pin = DIALOG.input(tr("PIN для открытия плитки", "Tile PIN"), option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if check_pin(pin, read_json(CONFIG / "pin.json")):
            return True
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    show_error(tr("Плитка закрыта", "Tile locked"))
    return False


def start_external(command, identifier, *arguments):
    try:
        run("/usr/lib/home-tv/session", command, identifier, *arguments, timeout=18)
    except (OSError, subprocess.SubprocessError):
        show_error(tr("Не удалось запустить приложение", "Could not start the application"))


def select_game():
    field = "name_ru" if russian() else "name_en"
    names = list(GAMES)
    choice = DIALOG.select(tr("Игры HomeTV Pi", "HomeTV Pi games"),
                           [GAMES[name][field] for name in names])
    if choice >= 0:
        launch(f"game:{names[choice]}")


def select_console(close):
    names = list(CONSOLES)
    field = "name_ru" if russian() else "name_en"
    choice = DIALOG.select(tr("Ретроконсоли", "Retro consoles"),
                           [CONSOLES[name][field] for name in names])
    if choice >= 0:
        launch(f"retrogames:{names[choice]}", close)


def launch(action, close=None):
    if action == "retrogames":
        select_console(close)
        return
    if not unlocked(action):
        return
    if action.startswith("web:"):
        start_external("open", action.removeprefix("web:"))
        return
    if action.startswith("game:"):
        start_external("game", action.removeprefix("game:"))
        return
    if action.startswith("retrogames:"):
        console_id = action.removeprefix("retrogames:")
        if console_id in CONSOLES:
            rom = select_rom(console_id)
            if rom is not None:
                if close is not None:
                    close()
                start_external("emulate", console_id, str(rom))
        return
    if action == "games":
        select_game()
        return
    if action == "phone":
        panel_url()
        return
    if close is not None:
        close()
    if action == "settings":
        device_settings()
    elif action in {"usb", "eject"}:
        choose_usb(eject=action == "eject")
    else:
        windows = {"files": "Videos,files", "library": "Videos,videodb://movies/titles/",
                   "music": "Music", "photos": "Pictures", "tv": "TVChannels"}
        if action in windows:
            xbmc.executebuiltin(f"ActivateWindow({windows[action]})")


class Home(xbmcgui.WindowXMLDialog):
    def onInit(self):
        local = [
            (tr("Видео и музыка", "Video and music"), tr("Файлы и сеть", "Files and network"), "files"),
            ("USB", tr("Подключённые диски", "Connected drives"), "usb"),
            (tr("Библиотека", "Library"), tr("Фильмы и сериалы", "Movies and TV shows"), "library"),
            (tr("Музыка", "Music"), tr("Альбомы и плейлисты", "Albums and playlists"), "music"),
            (tr("Фото", "Photos"), tr("Папки и слайд-шоу", "Folders and slideshows"), "photos"),
            (tr("Телевидение", "Live TV"), "IPTV / EPG", "tv"),
            (tr("Ретроконсоли", "Retro consoles"), "NES / Mega Drive / PS1", "retrogames"),
            (tr("Головоломки", "Puzzles"), "HomeTV Pi", "games"),
            (tr("Извлечь USB", "Eject USB"), tr("Отключение диска", "Safe removal"), "eject"),
            (tr("Пульт на телефоне", "Phone remote"), "QR", "phone"),
            (tr("Настройки", "Settings"), "HomeTV Pi", "settings"),
        ]
        try:
            web = [(entry["name"], entry.get("quality_note") or tr("Веб-сервис", "Web service"),
                    f"web:{service_id}") for service_id, entry in load_catalogue().items()]
        except (OSError, ValueError):
            web = []
            show_error(tr("Проверьте файл services.json", "Check services.json"))
        featured = [tile for key in ("web:youtube-tv", "web:ivi", "web:kion", "web:netflix")
                    for tile in web if tile[2] == key]
        self.tiles = [*local[:1], *featured, *local[1:], *(tile for tile in web if tile not in featured)]
        self.panel = self.getControl(100)
        self.panel.reset()
        self.panel.addItems([xbmcgui.ListItem(label, detail) for label, detail, _ in self.tiles])
        self.setFocusId(100)
        self.getControl(201).setLabel(tr("Медиацентр", "Media center"))
        if len(self.tiles) > 12:
            self.getControl(202).setLabel(tr("↓  Ещё плитки", "↓  More tiles"))

    def onClick(self, control_id):
        if control_id != 100:
            return
        index = self.panel.getSelectedPosition()
        if not 0 <= index < len(self.tiles):
            return
        launch(self.tiles[index][2], self.close)


if __name__ == "__main__":
    action = next((argument.removeprefix("action=") for argument in sys.argv[1:]
                   if argument.startswith("action=")), "")
    if action:
        launch(action)
    else:
        Home("HomeTV.xml", ADDON.getAddonInfo("path"), "default", "720p").doModal()
