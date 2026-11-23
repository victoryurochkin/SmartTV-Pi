"""Kodi file chooser for user-owned cartridge and disc images."""

import os
from pathlib import Path
import subprocess

import xbmcgui

from common import russian, show_error, tr, usb_drives
from hometv_retro import CONSOLES, rom_roots


def browse_roms(dialog, title, root, extensions):
    root = root.absolute()
    current = root
    back = "← " + tr("Назад", "Back")

    while True:
        if current.resolve(strict=True) != current:
            raise ValueError("Папка с играми изменилась или является символьной ссылкой")
        with os.scandir(current) as entries:
            visible = []
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                folder = entry.is_dir(follow_symlinks=False)
                if folder or (entry.is_file(follow_symlinks=False)
                              and Path(entry.name).suffix.lower() in extensions):
                    visible.append((entry, folder))
        visible.sort(key=lambda item: (not item[1], item[0].name.casefold()))
        labels = [("▸ " if folder else "") + entry.name for entry, folder in visible]
        choice = dialog.select(f"{title} · {current.name}", [back, *labels])
        if choice < 1:
            if current == root:
                return None
            current = current.parent
            continue

        entry, folder = visible[choice - 1]
        selected = Path(entry.path)
        resolved = selected.resolve(strict=True)
        if resolved != selected or not resolved.is_relative_to(root):
            continue
        if folder:
            if resolved.is_dir():
                current = resolved
        elif resolved.is_file():
            return resolved


def select_rom(console_id):
    console = CONSOLES[console_id]
    title = console["name_ru" if russian() else "name_en"]
    dialog = xbmcgui.Dialog()
    try:
        try:
            drives = usb_drives()
        except (OSError, ValueError, subprocess.SubprocessError):
            drives = []

        sources = rom_roots(console_id, drives)
        if not sources:
            dialog.ok(title, tr("Подключите USB с играми или добавьте файлы в локальную папку ROM.",
                                "Connect a USB drive with games or add files to the local ROM folder."))
            return None
        labels = [tr(label, "Internal storage") if index == 0 else label
                  for index, (label, _) in enumerate(sources)]
        while True:
            choice = dialog.select(tr("Источник игры", "Game source"), labels)
            if choice < 0:
                return None
            _, root = sources[choice]
            selected = browse_roms(dialog, title, root, console["extensions"])
            if selected is not None:
                return selected
    except (OSError, ValueError):
        show_error(tr("Не удалось открыть папку с играми", "Could not open the game folder"))
        return None
