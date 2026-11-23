import subprocess

import xbmc
import xbmcgui

from common import tr, usb_drives
from setup import setup_wizard


def main():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(1):
        return
    try:
        setup_wizard()
    except (OSError, ValueError):
        xbmc.log("HomeTV: could not open the setup wizard", xbmc.LOGWARNING)
    xbmc.executebuiltin("RunAddon(script.hometv)")
    previous = None
    while not monitor.abortRequested():
        try:
            drives = {drive["device"]: drive["label"] for drive in usb_drives()}
            if previous is not None:
                for device in drives.keys() - previous:
                    xbmcgui.Dialog().notification(
                        "USB", tr("Подключён накопитель — открыть в разделе USB",
                                  "Drive connected. Open it under USB") + f" · {drives[device]}", time=4500
                    )
            previous = drives.keys()
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        if monitor.waitForAbort(2):
            return


if __name__ == "__main__":
    main()
