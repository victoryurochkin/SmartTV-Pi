#!/bin/bash -e

rm -f "$ROOTFS_DIR/etc/hometv-build-packages"
install -m 0600 kodi-ru.zip "$ROOTFS_DIR/root/home-tv-kodi-ru.zip"
on_chroot <<'CHROOT'
unzip -qo /root/home-tv-kodi-ru.zip -d /usr/share/kodi/addons
rm -f /root/home-tv-kodi-ru.zip
CHROOT
for source in runtime rootfs; do
    rsync -rltp --chown=root:root --chmod=D0755,F0644 "$source/" "$ROOTFS_DIR/"
    while IFS= read -r -d '' path; do
        if head -c 2 "$path" | grep -axq '#!'; then
            chmod 0755 "$ROOTFS_DIR/${path#*/}"
        fi
    done < <(find "$source" -type f -print0)
done

if [[ -f $ROOTFS_DIR/etc/sudoers.d/home-tv-admin ]]; then
    chmod 0440 "$ROOTFS_DIR/etc/sudoers.d/home-tv-admin"
fi
rm -f "$ROOTFS_DIR"/etc/ssh/ssh_host_*_key{,.pub}
install -d "$ROOTFS_DIR"/etc/systemd/{system-generators,zram-generator.conf.d}
ln -sfn /dev/null "$ROOTFS_DIR/etc/systemd/system-generators/rpi-swap-generator"
ln -sfn /dev/null "$ROOTFS_DIR/etc/systemd/zram-generator.conf.d/20-rpi-swap-zram0-ctrl.conf"
install -d "$ROOTFS_DIR/etc/cloud"
touch "$ROOTFS_DIR/etc/cloud/cloud-init.disabled"

printf '%s\n' "$HOMETV_VERSION" > "$ROOTFS_DIR/etc/hometv-version"
printf 'project=%s\npi-gen=%s\n' "$HOMETV_PROJECT_COMMIT" "$GIT_HASH" > "$ROOTFS_DIR/etc/hometv-build"
install -d -m 0755 "$ROOTFS_DIR/data" "$ROOTFS_DIR/var/log/journal"
printf 'DATADEV /data ext4 defaults,nodev,nosuid,x-systemd.requires=home-tv-data-grow.service 0 0\n' >> "$ROOTFS_DIR/etc/fstab"
printf '/data/log/journal /var/log/journal none bind,x-systemd.requires-mounts-for=/data 0 0\n' >> "$ROOTFS_DIR/etc/fstab"
sed -i -E '/[[:space:]]\/boot\/firmware[[:space:]]/s/[[:space:]]+defaults[[:space:]]+/ defaults,ro /' "$ROOTFS_DIR/etc/fstab"
sed -i -e 's/ resize\b//' -e 's/^/overlayroot=tmpfs:recurse=0 /' "$ROOTFS_DIR/boot/firmware/cmdline.txt"
printf '\n[pi4]\nhdmi_enable_4kp60=1\n\n[all]\ndtparam=watchdog=on\n' >> "$ROOTFS_DIR/boot/firmware/config.txt"
manifest="$ROOTFS_DIR/usr/share/kodi/system/addon-manifest.xml"
grep -q '</addons>' "$manifest"
for addon in script.hometv plugin.hometv.widgets resource.language.ru_ru; do
    if [[ -f $ROOTFS_DIR/usr/share/kodi/addons/$addon/addon.xml ]] && ! grep -Fq ">$addon<" "$manifest"; then
        sed -i "/<\\/addons>/i\\    <addon>$addon</addon>" "$manifest"
    fi
done
install -m 0644 add-estuary-menu.py "$ROOTFS_DIR/root/hometv-add-estuary-menu.py"

printf '\noverlay\n' >> "$ROOTFS_DIR/etc/initramfs-tools/modules"
sed -i -e 's/^# *ru_RU.UTF-8 UTF-8$/ru_RU.UTF-8 UTF-8/' -e 's/^# *en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/' "$ROOTFS_DIR/etc/locale.gen"
ln -sfn /usr/share/zoneinfo/Etc/UTC "$ROOTFS_DIR/etc/localtime"
on_chroot <<'CHROOT'
python3 /root/hometv-add-estuary-menu.py /
rm -f /root/hometv-add-estuary-menu.py
usermod --home /data/home --shell /usr/sbin/nologin --password '!' --groups audio,video,render,input,plugdev,netdev hometv
passwd --lock root
test "$(id -u hometv):$(id -g hometv)" = 1000:1000
useradd --uid 1001 --user-group --home-dir /data/ssh-home --shell /bin/bash --password '!' tvadmin
test "$(id -u tvadmin):$(id -g tvadmin)" = 1001:1001
systemctl disable rpi-resize.service ssh.service ssh.socket
systemctl mask rpi-resize.service getty@tty1.service userconfig.service sshd-keygen.service
systemctl set-default graphical.target
for unit in home-tv-kodi.service home-tv-session.socket home-tv-panel.service home-tv-state.service; do
    if [ -f "/etc/systemd/system/$unit" ]; then
        systemctl enable "$unit"
    fi
done
locale-gen
update-locale LANG=ru_RU.UTF-8
update-initramfs -u -k all
CHROOT
