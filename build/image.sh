#!/usr/bin/env bash
set -euo pipefail

project=$(cd -- "$(dirname -- "$0")/.." && pwd)
pigen_commit=c0d2c9f2cffc08bc56850b0a3eb23178f4226e8a
builder_base=docker.io/library/debian:trixie@sha256:9c6e381421d0f48d1b8133e573f33c185ee16cbf505eda9c4a8a4791b25ea8a6
builder="hometv-pigen:${pigen_commit:0:12}"
version=${HOMETV_VERSION:-0.1.0}
cache=${HOMETV_BUILD_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/hometv-pi}
output=${HOMETV_OUTPUT:-$project/dist}
reuse=0

if [[ ${1:-} == --reuse-base ]]; then
    reuse=1
    shift
fi
if (($#)); then
    echo 'Использование: bash build/image.sh [--reuse-base]' >&2
    exit 2
fi
if [[ ! $version =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$ ]]; then
    echo 'HOMETV_VERSION должен содержать версию SemVer без префикса v.' >&2
    exit 2
fi
for command in docker flock git python3 xz; do
    command -v "$command" >/dev/null
done

mkdir -p -- "$cache" "$output"
cache=$(cd -- "$cache" && pwd)
output=$(cd -- "$output" && pwd)
case $(stat -f -c %T -- "$cache") in
    9p|drvfs|fuseblk|cifs|smb2)
        echo 'HOMETV_BUILD_CACHE должен находиться на файловой системе Linux, например в ~/.cache внутри WSL.' >&2
        exit 1
        ;;
esac

exec 9>"$cache/build.lock"
if ! flock -n 9; then
    echo 'В этом каталоге уже выполняется сборка HomeTV Pi.' >&2
    exit 1
fi
run=$(mktemp -d "$cache/run.XXXXXXXX")
trap 'rm -rf -- "$run"' EXIT
mkdir -p -- "$run/pi-gen" "$run/deploy"
if [[ ! -d $cache/pi-gen/.git ]]; then
    git clone --branch arm64 --single-branch https://github.com/RPi-Distro/pi-gen.git "$cache/pi-gen"
fi
if ! git -C "$cache/pi-gen" cat-file -e "$pigen_commit^{commit}"; then
    git -C "$cache/pi-gen" fetch --depth 1 origin "$pigen_commit"
fi
git -C "$cache/pi-gen" archive "$pigen_commit" | tar -x -C "$run/pi-gen"
cd -- "$run/pi-gen"

install -m 0644 "$project/build/pigen.conf" config
touch stage2/SKIP_IMAGES
work="$cache/work"
if ((reuse)); then
    base="$work/hometv-pi"
    if [[ ! -f $base/stage2/rootfs/etc/os-release ]]; then
        echo 'В кеше нет стадии stage2. Выполните сборку без --reuse-base.' >&2
        exit 1
    fi
    touch stage0/SKIP stage1/SKIP stage2/SKIP
fi
mkdir -p -- "$work"

packages_stage=stage-hometv-packages
appliance_stage=stage-hometv-appliance
mkdir -p "$packages_stage/00-packages" "$appliance_stage/00-appliance" export-image/04a-hometv-data-id
for stage in "$packages_stage" "$appliance_stage"; do
    printf '#!/bin/bash -e\nrm -rf -- "$ROOTFS_DIR"\ncopy_previous\n' > "$stage/prerun.sh"
done
cat >> "$packages_stage/prerun.sh" <<'PREFERENCES'
cat > "$ROOTFS_DIR/etc/apt/preferences.d/90-hometv" <<'APT'
Package: chromium chromium-common chromium-l10n chromium-sandbox kodi kodi-bin kodi-data kodi-pvr-iptvsimple
Pin: origin archive.raspberrypi.com
Pin-Priority: 600
APT
PREFERENCES
install -m 0644 "$project/build/packages" "$packages_stage/00-packages/00-packages-nr"
install -m 0755 "$project/build/stage3-packages.sh" "$packages_stage/00-packages/01-run.sh"
packages_key=$(sha256sum "$packages_stage/prerun.sh" "$packages_stage"/00-packages/* | sha256sum | cut -d ' ' -f 1)
if ((reuse)) && [[ -f $base/$packages_stage/rootfs/etc/hometv-build-packages ]] &&
    grep -Fxq "$packages_key" "$base/$packages_stage/rootfs/etc/hometv-build-packages"; then
    touch "$packages_stage/SKIP"
fi
install -m 0755 "$project/build/stage4-appliance.sh" "$appliance_stage/00-appliance/00-run.sh"
install -m 0755 "$project/build/export-data-id.sh" export-image/04a-hometv-data-id/00-run.sh
touch "$appliance_stage/EXPORT_IMAGE"
cp -a -- "$project/rootfs" "$appliance_stage/00-appliance/rootfs"
cp -a -- "$project/build/runtime" "$appliance_stage/00-appliance/runtime"
install -m 0755 "$project/build/append-data.sh" append-data.sh
install -m 0755 "$project/build/check-image.sh" check-image.sh
chmod 0755 "$packages_stage/prerun.sh" "$appliance_stage/prerun.sh"

docker build --build-arg "BASE_IMAGE=$builder_base" --tag "$builder" .
project_commit=$(git -C "$project" rev-parse HEAD)
img="HomeTV-Pi-${version}-arm64"
docker run --rm --privileged \
    --mount "type=bind,source=$work,target=/pi-gen/work" \
    --mount "type=bind,source=$run/deploy,target=/pi-gen/deploy" \
    -e "GIT_HASH=$pigen_commit" -e "HOMETV_PROJECT_COMMIT=$project_commit" \
    -e "HOMETV_VERSION=$version" -e "IMG_FILENAME=$img" -e "HOMETV_REUSE=$reuse" \
    -e "HOMETV_PACKAGES_KEY=$packages_key" \
    "$builder" bash -euo pipefail -c '
        cd /pi-gen
        mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc || true
        probe=$(mktemp -d)
        if ! arch-test -c "$probe" arm64; then
            test ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64-hometv
            printf "%s\n" ":qemu-aarch64-hometv:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xb7\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-aarch64:F" > /proc/sys/fs/binfmt_misc/register
            trap "echo -1 > /proc/sys/fs/binfmt_misc/qemu-aarch64-hometv" EXIT
        fi
        rmdir "$probe"
        # Keep a successful base for explicitly requested local rebuilds.
        if ((HOMETV_REUSE)); then ./build.sh; else CLEAN=1 ./build.sh; fi
        ./append-data.sh "deploy/$IMG_FILENAME.img"
        ./check-image.sh "deploy/$IMG_FILENAME.img"
        chmod 0644 "deploy/$IMG_FILENAME.img" "deploy/$IMG_FILENAME.packages.tsv"
    ' 2>&1 | tee "$output/build.log"

xz --threads=0 -3 --keep -- "$run/deploy/$img.img"
base_url=${HOMETV_RELEASE_URL:-https://github.com/victoryurochkin/SmartTV-Pi/releases/download/v$version}
python3 "$project/build/manifest.py" "$run/deploy/$img.img" "$version" "$base_url"
for file in "$img.img.xz" "$img.img.sha256" "$img.img.xz.sha256" "$img.packages.tsv" os-list.json; do
    cp -- "$run/deploy/$file" "$output/.$file.tmp"
    mv -f -- "$output/.$file.tmp" "$output/$file"
done
cp -- "$project/build/hometv-icon.svg" "$output/hometv-icon.svg"
printf 'Образ: %s/%s.img.xz\n' "$output" "$img"
