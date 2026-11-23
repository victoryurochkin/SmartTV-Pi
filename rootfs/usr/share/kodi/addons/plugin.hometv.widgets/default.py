"""Supply HomeTV Pi entries to Kodi's native Estuary widgets."""

import sys
from urllib.parse import parse_qs, urlencode, urlsplit

import xbmc
import xbmcgui
import xbmcplugin


sys.path.insert(0, "/usr/lib/home-tv")
from hometv_games import GAMES
from hometv_retro import CONSOLES
from hometv_streaming import load_catalogue, validate_service_id


MEDIA = (
    ("files", "Видео и музыка", "Video and music", "DefaultVideo.png"),
    ("usb", "Накопители USB", "USB drives", "DefaultHardDisk.png"),
    ("library", "Библиотека", "Library", "DefaultMovies.png"),
    ("music", "Музыка", "Music", "DefaultMusicSongs.png"),
    ("photos", "Фото", "Photos", "DefaultPicture.png"),
    ("tv", "Телевидение", "Live TV", "DefaultTVShows.png"),
    ("eject", "Извлечь USB", "Eject USB", "DefaultHardDisk.png"),
    ("phone", "Пульт на телефоне", "Phone remote", "DefaultAddonService.png"),
    ("settings", "Настройки", "Settings", "DefaultAddonProgram.png"),
)
FEATURED_SERVICES = ("youtube-tv", "ivi", "kion", "netflix")


def service_tiles():
    try:
        catalogue = load_catalogue()
    except (OSError, ValueError):
        xbmc.log("HomeTV Pi: не удалось прочитать каталог сервисов", xbmc.LOGWARNING)
        return
    ordered = dict.fromkeys((*FEATURED_SERVICES, *catalogue))
    for service_id in ordered:
        if service_id in catalogue:
            service = catalogue[service_id]
            yield (
                f"web:{service_id}", service["name"], service.get("quality_note", ""),
                service.get("icon") or "DefaultVideo.png",
            )


def media_tiles(russian):
    for action, russian_name, english_name, icon in MEDIA:
        yield action, russian_name if russian else english_name, "", icon


def game_tiles(russian):
    name_field = "name_ru" if russian else "name_en"
    for console_id, console in CONSOLES.items():
        yield f"retrogames:{console_id}", console[name_field], "", "DefaultAddonGame.png"


def run_action(action):
    prefix, _, value = action.partition(":")
    if (
        action in {item[0] for item in MEDIA} | {"retrogames"}
        or prefix == "web" and validate_service_id(value)
        or prefix == "game" and value in GAMES
        or prefix == "retrogames" and value in CONSOLES
    ):
        xbmc.executebuiltin(f"RunAddon(script.hometv,action={action})")


def main():
    path = urlsplit(sys.argv[0]).path.strip("/")
    handle = int(sys.argv[1])
    arguments = parse_qs(sys.argv[2].removeprefix("?"))
    if path == "play":
        run_action(arguments.get("action", [""])[0])
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    russian = xbmc.getLanguage(xbmc.ISO_639_1) == "ru"
    listings = {"services": service_tiles, "media": lambda: media_tiles(russian),
                "games": lambda: game_tiles(russian)}
    if path in listings:
        for action, title, detail, icon in listings[path]():
            item = xbmcgui.ListItem(label=title, label2=detail)
            item.setArt({"icon": icon, "thumb": icon})
            url = "plugin://plugin.hometv.widgets/play/?" + urlencode({"action": action})
            xbmcplugin.addDirectoryItem(handle, url, item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


if __name__ == "__main__":
    main()
