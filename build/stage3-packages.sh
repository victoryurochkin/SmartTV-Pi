#!/bin/bash -e

locale_url=https://mirrors.kodi.tv/addons/omega/resource.language.ru_ru/resource.language.ru_ru-11.0.106.zip
locale_sha256=41012f12aa888795316e74a0fc9e311bebf0c916cc01d1b08583a2ff867e6974
archive=$(mktemp)
target_archive=/tmp/home-tv-kodi-ru.zip
trap 'rm -f "$archive" "$ROOTFS_DIR$target_archive"' EXIT
curl --fail --silent --show-error --location --retry 3 "$locale_url" -o "$archive"
printf '%s  %s\n' "$locale_sha256" "$archive" | sha256sum --check
install -m 0644 "$archive" "$ROOTFS_DIR$target_archive"
on_chroot <<'CHROOT'
unzip -qo /tmp/home-tv-kodi-ru.zip -d /usr/share/kodi/addons
CHROOT
printf '%s\n' "$HOMETV_PACKAGES_KEY" > "$ROOTFS_DIR/etc/hometv-build-packages"
