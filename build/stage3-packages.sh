#!/bin/bash -e

install -d -m 0755 "$ROOTFS_DIR/usr/lib/home-tv/cores"
for core in nestopia genesis_plus_gx; do
    library="/usr/lib/aarch64-linux-gnu/libretro/${core}_libretro.so"
    test -f "$ROOTFS_DIR$library"
    ln -s "$library" "$ROOTFS_DIR/usr/lib/home-tv/cores/${core}_libretro.so"
done

profiles=$(mktemp -d)
trap 'rm -rf -- "$profiles"; rm -f -- "$ROOTFS_DIR/root/pcsx-rearmed.tar.gz"' EXIT
tar -xzf joypad-autoconfig.tar.gz --strip-components=1 -C "$profiles"
install -d -m 0755 "$ROOTFS_DIR/usr/share/home-tv/retroarch/autoconfig" "$ROOTFS_DIR/usr/share/doc/home-tv-joypad-autoconfig"
cp -a -- "$profiles/udev" "$ROOTFS_DIR/usr/share/home-tv/retroarch/autoconfig/"
install -m 0644 "$profiles/COPYING" "$ROOTFS_DIR/usr/share/doc/home-tv-joypad-autoconfig/COPYING"

install -m 0600 pcsx-rearmed.tar.gz "$ROOTFS_DIR/root/pcsx-rearmed.tar.gz"
on_chroot <<'CHROOT'
source_dir=$(mktemp -d /var/tmp/hometv-pcsx-rearmed.XXXXXXXX)
trap 'rm -rf -- "$source_dir"' EXIT
tar -xzf /root/pcsx-rearmed.tar.gz --strip-components=1 -C "$source_dir"
cd "$source_dir"
make -j4 -f Makefile.libretro platform=unix DYNAREC=ari64 BUILTIN_GPU=neon HAVE_PHYSICAL_CDROM=0 HAVE_CHD=1
test -s libpcsxcore/new_dynarec/linkage_arm64.o
test -s libpcsxcore/new_dynarec/new_dynarec.o
readelf -h pcsx_rearmed_libretro.so | grep -Eq 'Machine:.*AArch64'
readelf -W --dyn-syms pcsx_rearmed_libretro.so | grep -Eq '[[:space:]]retro_init$'
install -m 0644 pcsx_rearmed_libretro.so /usr/lib/home-tv/cores/pcsx_rearmed_libretro.so
install -Dm 0644 COPYING /usr/share/doc/home-tv-pcsx-rearmed/COPYING
CHROOT

printf '%s\n' "$HOMETV_PACKAGES_KEY" > "$ROOTFS_DIR/etc/hometv-build-packages"
