from datetime import date
from hashlib import file_digest
import json
from pathlib import Path
import sys
from urllib.parse import urlparse


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def write_release(image: Path, version: str, base_url: str) -> None:
    url = urlparse(base_url)
    if url.scheme != "https" or not url.netloc or url.query or url.fragment:
        raise ValueError("HOMETV_RELEASE_URL должен быть базовым HTTPS-адресом выпуска")
    base_url = base_url.rstrip("/")
    compressed = image.with_suffix(".img.xz")
    raw_hash = sha256(image)
    compressed_hash = sha256(compressed)
    for path, checksum in ((image, raw_hash), (compressed, compressed_hash)):
        path.with_suffix(path.suffix + ".sha256").write_text(
            f"{checksum}  {path.name}\n", encoding="ascii"
        )

    listing = {
        "os_list": [
            {
                "name": f"HomeTV Pi {version}",
                "description": "Медиацентр с Kodi и официальными веб-сервисами",
                "url": f"{base_url}/{compressed.name}",
                "icon": f"{base_url}/hometv-icon.svg",
                "website": "https://github.com/victoryurochkin/SmartTV-Pi",
                "release_date": date.today().isoformat(),
                "extract_size": image.stat().st_size,
                "extract_sha256": raw_hash,
                "image_download_size": compressed.stat().st_size,
                "image_download_sha256": compressed_hash,
                "architecture": "armv8",
                "devices": ["pi3-64bit", "pi4-64bit"],
                "init_format": "none",
            }
        ]
    }
    (image.parent / "os-list.json").write_text(
        json.dumps(listing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    write_release(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
