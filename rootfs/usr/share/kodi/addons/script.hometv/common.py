import json
import subprocess

import xbmc
import xbmcgui


def russian():
    return xbmc.getLanguage(xbmc.ISO_639_1) == "ru"


def tr(ru, en):
    return ru if russian() else en


def run(*args, timeout=12, input_text=None):
    return subprocess.run(
        args, input=input_text, capture_output=True, text=True, check=True, timeout=timeout
    ).stdout


def usb_drives():
    return json.loads(run("/usr/lib/home-tv/usb", "list", timeout=4))


def show_error(message):
    xbmcgui.Dialog().notification("HomeTV Pi", message, xbmcgui.NOTIFICATION_ERROR)
