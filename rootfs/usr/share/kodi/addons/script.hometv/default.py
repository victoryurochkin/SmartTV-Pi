import os
from pathlib import Path
import subprocess

import xbmc
import xbmcaddon
import xbmcgui

from common import run, show_error, tr, usb_drives


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


class Home(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.tiles = [
            (tr("Видео и музыка", "Video and music"), tr("Файлы и сеть", "Files and network"), "files"),
            ("USB", tr("Подключённые диски", "Connected drives"), "usb"),
            (tr("Библиотека", "Library"), tr("Фильмы и сериалы", "Movies and TV shows"), "library"),
            (tr("Музыка", "Music"), tr("Альбомы и плейлисты", "Albums and playlists"), "music"),
            (tr("Фото", "Photos"), tr("Папки и слайд-шоу", "Folders and slideshows"), "photos"),
            (tr("Телевидение", "Live TV"), "IPTV / EPG", "tv"),
            (tr("Извлечь USB", "Eject USB"), tr("Безопасное отключение", "Safe removal"), "eject"),
            (tr("Настройки", "Settings"), "Kodi", "settings"),
        ]
        self.panel = self.getControl(100)
        self.panel.reset()
        self.panel.addItems([xbmcgui.ListItem(label, detail) for label, detail, _ in self.tiles])
        self.setFocusId(100)
        self.getControl(201).setLabel(tr("Медиацентр", "Media center"))

    def onClick(self, control_id):
        if control_id != 100:
            return
        index = self.panel.getSelectedPosition()
        if not 0 <= index < len(self.tiles):
            return
        action = self.tiles[index][2]
        self.close()
        if action in {"usb", "eject"}:
            choose_usb(eject=action == "eject")
            return
        windows = {"files": "Videos,files", "library": "Videos,videodb://movies/titles/",
                   "music": "Music", "photos": "Pictures", "tv": "TVChannels", "settings": "Settings"}
        xbmc.executebuiltin(f"ActivateWindow({windows[action]})")


if __name__ == "__main__":
    Home("HomeTV.xml", ADDON.getAddonInfo("path"), "default", "720p").doModal()
