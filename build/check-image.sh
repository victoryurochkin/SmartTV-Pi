#!/usr/bin/env bash
set -euo pipefail

image=${1:?Укажите путь к .img}
scratch=$(mktemp -d)
disk=
cleanup() {
    if [[ -n $disk ]]; then
        for directory in data boot root; do
            if mountpoint -q "$scratch/$directory"; then
                umount "$scratch/$directory"
            fi
        done
        losetup -d "$disk"
    fi
    rmdir "$scratch"/{data,boot,root} "$scratch"
}
trap cleanup EXIT
mkdir "$scratch"/{data,boot,root}
# pi-gen supplies loop-device helpers for Docker environments without udev.
source /pi-gen/scripts/common
ensure_next_loopdev
disk=$(losetup --find --show --read-only --partscan "$image")
ensure_loopdev_partitions "$disk"
mount -t vfat -o ro "${disk}p1" "$scratch/boot"
mount -t ext4 -o ro,noload "${disk}p2" "$scratch/root"
mount -t ext4 -o ro,noload "${disk}p3" "$scratch/data"

root="$scratch/root"
boot="$scratch/boot"
data="$scratch/data"
boot_id=$(blkid -s PARTUUID -o value "${disk}p1")
root_id=$(blkid -s PARTUUID -o value "${disk}p2")
data_id=$(blkid -s PARTUUID -o value "${disk}p3")
grep -qw "root=PARTUUID=$root_id" "$boot/cmdline.txt"
grep -qw 'overlayroot=tmpfs:recurse=0' "$boot/cmdline.txt"
grep -q "^PARTUUID=$boot_id .*boot/firmware .*defaults,ro" "$root/etc/fstab"
grep -q "^PARTUUID=$data_id /data ext4 " "$root/etc/fstab"
test -f "$boot/kernel8.img"
test -f "$boot/initramfs8"
for model in bcm2710-rpi-3-b bcm2710-rpi-3-b-plus bcm2711-rpi-4-b; do
    test -f "$boot/$model.dtb"
done
[[ $(stat -c '%a %u:%g' "$data/home") == '700 1000:1000' ]]
[[ $(stat -c '%a %u:%g' "$data/config") == '700 1000:1000' ]]
[[ $(stat -c '%a %u:%g' "$data/system") == '700 0:0' ]]
grep -Eq '^hometv:!:' "$root/etc/shadow"
grep -Eq '^tvadmin:!:' "$root/etc/shadow"
grep -Eq '^root:[!*]+:' "$root/etc/shadow"
if systemctl --root="$root" is-enabled --quiet ssh.service; then
    echo 'SSH должен быть выключен в заводском образе.' >&2
    exit 1
fi
test -x "$root/usr/lib/home-tv/data-grow"
test -x "$root/usr/bin/kodi"
test -x "$root/usr/lib/aarch64-linux-gnu/kodi/kodi.bin"
test -x "$root/usr/bin/chromium"
test -x "$root/usr/bin/retroarch"
for core in nestopia genesis_plus_gx; do
    library="${core}_libretro.so"
    test -f "$root/usr/lib/aarch64-linux-gnu/libretro/$library"
    [[ $(readlink "$root/usr/lib/home-tv/cores/$library") == "/usr/lib/aarch64-linux-gnu/libretro/$library" ]]
done
test -s "$root/usr/lib/home-tv/cores/pcsx_rearmed_libretro.so"
test -s "$root/usr/share/doc/home-tv-pcsx-rearmed/COPYING"
test -s "$root/usr/share/doc/home-tv-joypad-autoconfig/COPYING"
test -n "$(find "$root/usr/share/home-tv/retroarch/autoconfig/udev" -maxdepth 1 -name '*.cfg' -print -quit)"
for game in lbreakouthd sgt-bridges sgt-fifteen sgt-lightup sgt-mines sgt-solo; do
    test -x "$root/usr/games/$game"
done
test -f "$root/usr/share/kodi/addons/resource.language.ru_ru/addon.xml"
test -f "$root/usr/share/kodi/addons/plugin.hometv.widgets/addon.xml"
grep -Fq 'plugin://plugin.hometv.widgets/services/' "$root/usr/share/kodi/addons/skin.estuary/xml/Home.xml"
grep -Fq '<addon>resource.language.ru_ru</addon>' "$root/usr/share/kodi/system/addon-manifest.xml"
systemctl --root="$root" is-enabled --quiet home-tv-kodi.service
chroot "$root" /usr/bin/python3 -B -c 'import platform, ssl; assert platform.machine() == "aarch64"'
chroot "$root" /usr/sbin/visudo -c -q
dpkg-query --admindir="$root/var/lib/dpkg" -W -f='${db:Status-Abbrev}\t${Package}\t${Version}\t${Architecture}\n' |
    awk -F '\t' '$1 ~ /^ii/ {print $2 "\t" $3 "\t" $4}' | sort > "${image%.img}.packages.tsv"
printf 'Проверены разметка, файлы загрузки и базовый запуск userspace arm64.\n'
