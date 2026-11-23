import json
from pathlib import Path
import re
import subprocess

import xbmc
import xbmcgui

from common import run, show_error, tr
from hometv_state import CONFIG, check_pin, make_pin, read_json, write_json


DIALOG = xbmcgui.Dialog()
SETUP = CONFIG / "setup.json"
PIN = CONFIG / "pin.json"


def apply_kodi_setting(name, value):
    reply = xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1,
                                          "method": "Settings.SetSettingValue",
                                          "params": {"setting": name, "value": value}}))
    return json.loads(reply).get("result", False)


def admin(action, **params):
    result = subprocess.run(["/usr/bin/sudo", "-n", "/usr/lib/home-tv/admin"],
                            input=json.dumps({"action": action, **params}), capture_output=True,
                            text=True, timeout=35)
    data = json.loads(result.stdout)
    if result.returncode:
        raise ValueError(data.get("error", "HomeTV Pi"))
    return data


def select_wifi():
    try:
        networks = admin("wifi-scan")
        options = [f'{network["ssid"]} · {network["signal"]}%' for network in networks]
        index = DIALOG.select("Wi-Fi", [*options, tr("Другая сеть…", "Other network…")])
        if index < 0:
            return
        if index == len(options):
            ssid = DIALOG.input("SSID")
            secured = DIALOG.yesno("Wi-Fi", tr("Сеть требует пароль?", "Does the network require a password?"))
        else:
            ssid = networks[index]["ssid"]
            secured = networks[index]["security"] not in {"", "--"}
        if not ssid:
            return
        password = DIALOG.input(tr("Пароль Wi-Fi", "Wi-Fi password"), option=xbmcgui.ALPHANUM_HIDE_INPUT) if secured else ""
        if secured and not password:
            return
        admin("wifi-connect", ssid=ssid, password=password, hidden=index == len(options))
        DIALOG.notification("Wi-Fi", tr("Подключено", "Connected"))
    except (OSError, ValueError, subprocess.SubprocessError):
        show_error(tr("Не удалось подключить Wi-Fi. Проверьте сеть и пароль.", "Check the Wi-Fi network and password."))


def set_pin():
    if PIN.is_file():
        current = DIALOG.input(tr("Текущий PIN", "Current PIN"), option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if not check_pin(current, read_json(PIN)):
            return False
    title = tr("PIN веб-панели: 6–12 цифр", "Web panel PIN: 6–12 digits")
    pin = DIALOG.input(title, option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if not pin:
        return False
    repeat = DIALOG.input(tr("Повторите PIN", "Confirm PIN"), option=xbmcgui.ALPHANUM_HIDE_INPUT)
    try:
        if pin != repeat:
            raise ValueError
        write_json(PIN, make_pin(pin))
        return True
    except (OSError, ValueError):
        show_error(tr("PIN должен совпадать и содержать 6–12 цифр", "Use matching PINs of 6–12 digits"))
        return False


def setup_wizard():
    if not CONFIG.is_dir() or (read_json(SETUP, {}) or {}).get("complete"):
        return
    choice = DIALOG.select("Язык / Language", ["Русский", "English"])
    if choice < 0:
        return
    language = "ru" if choice == 0 else "en"
    apply_kodi_setting("locale.language", "resource.language.ru_ru" if choice == 0 else "resource.language.en_gb")
    zones = ["Europe/Moscow", "Europe/Kaliningrad", "Asia/Yekaterinburg", "Asia/Novosibirsk", "UTC"]
    choice = DIALOG.select(tr("Часовой пояс", "Time zone"), [*zones, tr("Другой…", "Other…")])
    zone = zones[choice] if 0 <= choice < len(zones) else ""
    if choice == len(zones):
        zone = DIALOG.input(tr("Часовой пояс IANA", "IANA time zone"))
    if zone:
        try:
            admin("timezone", zone=zone)
        except (OSError, ValueError, subprocess.SubprocessError):
            show_error(tr("Не удалось сохранить часовой пояс", "Could not save the time zone"))
            zone = ""
    keyboard = "us,ru" if DIALOG.select(tr("Раскладка", "Keyboard layout"), ["English", "English / Русский"]) == 1 else "us"
    if keyboard == "us,ru":
        apply_kodi_setting("locale.keyboardlayouts", ["English QWERTY", "Russian ЙЦУКЕН"])
    if DIALOG.yesno("Wi-Fi", tr("Настроить Wi-Fi? Ethernet подключается автоматически.",
                                 "Set up Wi-Fi? Ethernet connects automatically.")):
        select_wifi()
    if DIALOG.yesno("HomeTV Pi", tr("Задать PIN для пульта на телефоне?", "Set a PIN for the phone remote?")):
        set_pin()
    write_json(SETUP, {"complete": True, "language": language, "zone": zone, "keyboard": keyboard})


def audio_menu():
    try:
        sinks = json.loads(run("/usr/bin/pactl", "-f", "json", "list", "sinks"))
        if not sinks:
            raise ValueError
        choice = DIALOG.select(tr("Аудиовыход PipeWire", "PipeWire audio output"),
                               [sink["description"] for sink in sinks])
        if choice >= 0:
            run("/usr/bin/pactl", "set-default-sink", sinks[choice]["name"])
    except (OSError, ValueError, subprocess.SubprocessError):
        show_error(tr("Нет аудиовыходов PipeWire. Проверить звук Kodi можно в системных настройках.",
                      "No PipeWire outputs. Check local Kodi audio in system settings."))


def bluetooth_menu():
    try:
        tool = "/usr/bin/bluetoothctl"
        run(tool, "power", "on")
        DIALOG.notification("Bluetooth", tr("Идёт поиск устройств", "Scanning for devices"))
        run(tool, "--timeout", "8", "scan", "on", timeout=12)
        listing = run(tool, "devices")
        devices = []
        for row in listing.splitlines():
            match = re.fullmatch(r"Device ([0-9A-Fa-f:]{17}) (.+)", row)
            if match:
                devices.append(match.groups())
        if not devices:
            DIALOG.ok("Bluetooth", tr("Переведите устройство в режим сопряжения.",
                                      "Put the device in pairing mode."))
            return
        choice = DIALOG.select("Bluetooth", [f"{name} · {address}" for address, name in devices])
        if choice < 0:
            return
        address, _ = devices[choice]
        info = run(tool, "info", address)
        if "Paired: yes" not in info:
            run(tool, "--agent", "NoInputNoOutput", "--timeout", "25", "pair", address, timeout=28)
            if "Paired: yes" not in run(tool, "info", address):
                raise ValueError
        run(tool, "trust", address)
        if "Connected: yes" not in run(tool, "info", address):
            run(tool, "--timeout", "12", "connect", address, timeout=15)
        DIALOG.notification("Bluetooth", tr("Устройство сопряжено", "Device paired"))
    except (OSError, ValueError, subprocess.SubprocessError):
        show_error(tr("Сопряжение не завершилось. Устройства с кодом требуют отдельной настройки.",
                      "Pairing failed. Devices with passkeys require separate setup."))


def panel_url():
    data = read_json(Path("/run/home-tv-panel/addresses.json"), {})
    addresses = data.get("urls", []) if data else []
    if not PIN.is_file():
        set_pin()
        return
    if not addresses:
        DIALOG.ok("HomeTV Pi", tr("Подключите приставку к локальной сети и дождитесь запуска панели.",
                                  "Connect to your network and wait for the web panel to start."))
        return
    index = DIALOG.select(tr("Адрес пульта", "Remote address"), addresses) if len(addresses) > 1 else 0
    if index < 0:
        return
    url = addresses[index]
    import qrcode

    class Pairing(xbmcgui.WindowXMLDialog):
        def onInit(self):
            self.getControl(210).setImage(str(png))
            self.getControl(211).setLabel(url)
            self.getControl(212).setLabel(data.get("fingerprint", ""))

    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        png = Path(temporary) / "address.png"
        qrcode.make(url).save(png)
        Pairing("Pairing.xml", str(Path(__file__).parent), "default", "720p").doModal()
