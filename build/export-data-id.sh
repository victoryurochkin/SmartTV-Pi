#!/bin/bash -e
image="$STAGE_WORK_DIR/$IMG_FILENAME$IMG_SUFFIX.img"
disk_id=$(sfdisk --disk-id "$image")
[[ $disk_id =~ ^0x[0-9a-fA-F]{8}$ ]]
sed -i "s/^DATADEV /PARTUUID=${disk_id#0x}-03 /" "$ROOTFS_DIR/etc/fstab"
