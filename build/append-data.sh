#!/usr/bin/env bash
set -euo pipefail

image=${1:?Укажите путь к .img}
parts=$(sfdisk --dump "$image")
grep -qx 'label: dos' <<< "$parts"
[[ $(grep -c 'start=' <<< "$parts") == 2 ]]
disk_id=$(sfdisk --disk-id "$image")
bytes=$(stat -c %s "$image")
mib=1048576
start_mib=$(((bytes + mib - 1) / mib))
size_mib=256
truncate -s "$(((start_mib + size_mib) * mib))" "$image"
printf 'start=%d, size=%d, type=83\n' "$((start_mib * 2048))" "$((size_mib * 2048))" |
    sfdisk --no-reread --append "$image"
[[ $(sfdisk --disk-id "$image") == "$disk_id" ]]
sfdisk --verify "$image"

temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
install -m 0700 -o 1000 -g 1000 -d "$temp/data/home" "$temp/data/config"
install -m 0700 -o 1001 -g 1001 -d "$temp/data/ssh-home"
install -m 0700 -d "$temp/data/system"
install -m 0755 -d "$temp/data/log"
install -m 2755 -d "$temp/data/log/journal"
mkfs.ext4 -q -F -b 4096 -L HOMETV_DATA -m 0 -d "$temp/data" "$temp/data.ext4" "$((size_mib * 256))"
dd if="$temp/data.ext4" of="$image" bs=1M seek="$start_mib" conv=notrunc,sparse status=none
