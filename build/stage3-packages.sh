#!/bin/bash -e

locale_url=https://mirrors.kodi.tv/addons/omega/resource.language.ru_ru/resource.language.ru_ru-11.0.106.zip
locale_sha256=41012f12aa888795316e74a0fc9e311bebf0c916cc01d1b08583a2ff867e6974
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT
curl --fail --silent --show-error --location --retry 3 "$locale_url" -o "$archive"
printf '%s  %s\n' "$locale_sha256" "$archive" | sha256sum --check
unzip -qo "$archive" -d "$ROOTFS_DIR/usr/share/kodi/addons"
printf '%s\n' "$HOMETV_PACKAGES_KEY" > "$ROOTFS_DIR/etc/hometv-build-packages"
