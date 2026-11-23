import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile


CONFIG = Path("/data/config")
ROOT_STATE = Path("/data/system")


def read_json(path, default=None):
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError:
        return default


def write_atomic(path, payload, mode=0o600):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path, value):
    write_atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def make_pin(pin):
    if not isinstance(pin, str) or not pin.isascii() or not pin.isdigit() or not 6 <= len(pin) <= 12:
        raise ValueError("PIN должен содержать от 6 до 12 цифр")
    salt = secrets.token_bytes(16)
    return {"salt": salt.hex(), "hash": hashlib.scrypt(pin.encode(), salt=salt, n=16384, r=8, p=1).hex()}


def check_pin(pin, record):
    if not isinstance(pin, str) or len(pin) > 12 or not record:
        return False
    try:
        value = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(record["salt"]), n=16384, r=8, p=1)
        return hmac.compare_digest(value.hex(), record["hash"])
    except (KeyError, TypeError, ValueError):
        return False


def restore_timezone():
    name = read_json(ROOT_STATE / "timezone.json")
    if name is None:
        return
    zones = Path("/usr/share/zoneinfo")
    target = (zones / name).resolve(strict=True)
    if not target.is_relative_to(zones):
        raise ValueError("Недопустимый часовой пояс")
    temporary = Path("/etc/.hometv-localtime")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    temporary.replace("/etc/localtime")


if __name__ == "__main__":
    restore_timezone()
