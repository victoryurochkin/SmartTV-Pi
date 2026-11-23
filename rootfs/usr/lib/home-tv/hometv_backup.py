"""Export and restore portable settings on a mounted media device."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import fcntl
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from zlib import error as CompressionError

from hometv_state import CONFIG, write_atomic
from hometv_streaming import text_field, validate_catalogue, validate_service_id


FILES = ("services.json", "setup.json", "parental.json")
MAX_ENTRY = 256 * 1024
MAX_ARCHIVE = 1024 * 1024
MANIFEST = {"format": "home-tv-settings", "version": 1}
FILENAME = re.compile(r"home-tv-settings-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\.zip\Z")
SERVICE_FIELDS = (
    "id", "name", "url", "icon", "quality_note", "user_agent", "flags", "zoom", "prefer_h264"
)


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Повторяющееся поле JSON")
        result[key] = value
    return result


def invalid_constant(_value):
    raise ValueError("Некорректное число JSON")


def decode(payload):
    return json.loads(payload, object_pairs_hook=json_object, parse_constant=invalid_constant)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def portable_url(value):
    address = urlsplit(value)
    if not address.scheme:
        return value
    if address.scheme != "https" or address.username is not None:
        raise ValueError("В переносимых настройках разрешены только HTTPS-ссылки без учётных данных")
    return urlunsplit((address.scheme, address.netloc, address.path, "", ""))


def portable(name, payload):
    value = decode(payload)
    if not isinstance(value, dict):
        raise ValueError(f"Некорректные настройки {name}")
    if name == "services.json":
        copied = []
        for item in validate_catalogue(value).values():
            service = {key: item[key] for key in SERVICE_FIELDS if key in item}
            service["url"] = portable_url(service["url"])
            if service.get("icon", "").startswith(("http:", "https:")):
                try:
                    service["icon"] = portable_url(service["icon"])
                except ValueError:
                    service.pop("icon")
            copied.append(service)
        return encode({"services": copied})
    if name == "setup.json":
        settings = {}
        if value.get("language") in ("ru", "en"):
            settings["language"] = value["language"]
        if value.get("keyboard") in ("us", "us,ru"):
            settings["keyboard"] = value["keyboard"]
        if text_field(value.get("zone"), 120):
            try:
                ZoneInfo(value["zone"])
            except (ValueError, ZoneInfoNotFoundError) as error:
                raise ValueError("Некорректный часовой пояс в резервной копии") from error
            settings["zone"] = value["zone"]
        if text_field(value.get("audio"), 120):
            settings["audio"] = value["audio"]
        return encode(settings)
    locked = value.get("locked")
    if not isinstance(locked, list) or len(locked) > 120 or not all(map(validate_service_id, locked)):
        raise ValueError("Некорректный список заблокированных разделов")
    return encode({"locked": list(dict.fromkeys(locked))})


def read_file(name, maximum, *, directory=None, required=True):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        if not required:
            return None
        raise
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("Ожидался обычный файл допустимого размера")
        payload = stream.read(maximum + 1)
        if len(payload) > maximum:
            raise ValueError("Файл превышает допустимый размер")
        return payload


@contextmanager
def open_usb(device):
    result = subprocess.run(
        ["/usr/lib/home-tv/usb", "list"], capture_output=True, check=True, timeout=5
    )
    paths = {entry["path"] for entry in decode(result.stdout) if entry["device"] == device}
    if len(paths) != 1:
        raise ValueError("Выберите подключённый USB-раздел")
    path = Path(paths.pop())
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(descriptor).st_dev == path.parent.stat().st_dev:
            raise ValueError("USB-раздел уже извлечён")
        yield path, descriptor
    finally:
        os.close(descriptor)


@contextmanager
def backup_lock():
    lock = os.open(CONFIG / ".backup.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Уже выполняется резервное копирование или восстановление") from error
        yield
    finally:
        os.close(lock)


def sync_directory(descriptor):
    try:
        os.fsync(descriptor)
    except OSError as error:
        if error.errno not in (errno.EINVAL, errno.ENOTSUP):
            raise


def export_backup(device):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"home-tv-settings-{stamp}-{secrets.token_hex(4)}.zip"
    temporary = f".{name}.partial"
    with backup_lock(), open_usb(device) as (path, directory):
        entries = {"manifest.json": encode(MANIFEST)}
        for setting in FILES:
            content = read_file(CONFIG / setting, MAX_ENTRY, required=False)
            if content is not None:
                entries[setting] = portable(setting, content)

        descriptor = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        try:
            with os.fdopen(descriptor, "w+b") as stream:
                with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
                    for entry, content in entries.items():
                        archive.writestr(entry, content)
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            sync_directory(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
        return str(path / name)


def list_backups(device):
    with open_usb(device) as (_, directory), os.scandir(directory) as entries:
        return sorted(
            (entry.name for entry in entries
             if FILENAME.fullmatch(entry.name) and entry.is_file(follow_symlinks=False)),
            reverse=True,
        )


def read_archive(payload):
    with ZipFile(BytesIO(payload)) as archive:
        members = archive.infolist()
        names = {entry.filename for entry in members}
        if len(names) != len(members) or "manifest.json" not in names:
            raise ValueError("Повторяющиеся файлы или отсутствует манифест ZIP")
        for info in members:
            mode = stat.S_IFMT(info.external_attr >> 16)
            if (
                info.filename not in (*FILES, "manifest.json")
                or info.orig_filename != info.filename
                or mode not in (0, stat.S_IFREG)
                or info.file_size > MAX_ENTRY
                or info.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                or info.flag_bits & 1
            ):
                raise ValueError("ZIP содержит неподдерживаемые записи")
        if decode(archive.read("manifest.json")) != MANIFEST:
            raise ValueError("Неподдерживаемый формат резервной копии")
        return {name: portable(name, archive.read(name)) for name in FILES if name in names}


def restore_backup(device, filename):
    if not isinstance(filename, str) or not FILENAME.fullmatch(filename):
        raise ValueError("Выберите ZIP с настройками HomeTV Pi")
    with backup_lock(), open_usb(device) as (_, directory):
        payload = read_file(filename, MAX_ARCHIVE, directory=directory)
        try:
            updates = read_archive(payload)
        except (BadZipFile, CompressionError, NotImplementedError) as error:
            raise ValueError("Не удалось прочитать ZIP с настройками") from error
        original = {name: read_file(CONFIG / name, MAX_ENTRY, required=False) for name in updates}
        if "setup.json" in updates:
            settings = decode(original["setup.json"]) if original["setup.json"] else {}
            settings.update(decode(updates["setup.json"]))
            updates["setup.json"] = encode(settings)

        attempted = []
        try:
            for name, content in updates.items():
                attempted.append(name)
                write_atomic(CONFIG / name, content)
        except OSError as error:
            try:
                for name in reversed(attempted):
                    if original[name] is None:
                        (CONFIG / name).unlink(missing_ok=True)
                    else:
                        write_atomic(CONFIG / name, original[name])
                directory = os.open(CONFIG, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    sync_directory(directory)
                finally:
                    os.close(directory)
            except OSError as rollback_error:
                raise RuntimeError("Восстановление прервано, откат настроек не завершился") from rollback_error
            raise RuntimeError("Восстановление прервано, сохранены прежние настройки") from error
        return list(updates)


def main():
    parser = argparse.ArgumentParser(description="Копирование настроек HomeTV Pi на USB")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("export").add_argument("device")
    commands.add_parser("list").add_argument("device")
    restore = commands.add_parser("restore")
    restore.add_argument("device")
    restore.add_argument("filename")
    args = parser.parse_args()
    try:
        if args.command == "export":
            print(export_backup(args.device))
        elif args.command == "list":
            print(json.dumps(list_backups(args.device)))
        else:
            print(json.dumps(restore_backup(args.device, args.filename)))
    except (ValueError, OSError, RuntimeError, BadZipFile, CompressionError, subprocess.SubprocessError) as error:
        print(f"Резервная копия: {error}", file=sys.stderr)
        return 1
    return 0
