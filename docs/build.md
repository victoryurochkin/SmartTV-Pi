# Сборка образа

На Linux потребуются Bash, curl, Git, Python 3.11 или новее, xz, util-linux и работающий Docker Engine. Сборщик запускает привилегированный контейнер для работы с chroot и loop-устройствами. Понадобятся доступ к Docker Hub, GitHub, репозиториям Debian и Raspberry Pi, а также к зеркалу переводов Kodi. Скачанный архив перевода сохраняется в кеше сборки и при каждом использовании сверяется по SHA256.

Из корня репозитория на Linux выполните команду сборки.

```bash
bash build/image.sh
```

На Windows с Docker Engine внутри WSL 2 команду можно запустить из PowerShell.

```powershell
wsl -d Ubuntu --cd /mnt/d/Projects/SmartTV -- bash build/image.sh
```

Укажите своё расположение репозитория, если оно отличается. Промежуточные файловые системы хранятся внутри Linux в `~/.cache/hometv-pi`. Выходные файлы сохраняются в `dist/` репозитория. `HOMETV_BUILD_CACHE` задаёт другой каталог на файловой системе Linux, `HOMETV_OUTPUT` задаёт каталог результатов. Для повторной локальной сборки из успешно загруженной базовой системы используйте `bash build/image.sh --reuse-base`. Обычный запуск собирает стадии заново.

Скрипт закрепляет ревизию `pi-gen` и дайджест базового контейнера. Списки пакетов обновляются из подписанных репозиториев Debian и Raspberry Pi. В итоге сборка повторяет конфигурацию образа, а версии пакетов и содержимое могут отличаться по мере обновления репозиториев. Точные версии установленных пакетов сохраняются в TSV.

Для Pi 4 сборщик задаёт `hdmi_enable_4kp60=1` в секции `[pi4]`. Режим 4K при 60 Гц рассчитан на порт HDMI0 и совместимые телевизор и кабель. Температуру и троттлинг в этом режиме нужно измерить на плате. [Настройки HDMI Raspberry Pi](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/configuration/audio-display.adoc)

## Результат сборки

Ниже приведены имена файлов для `HOMETV_VERSION=0.3.0`.

- `HomeTV-Pi-0.3.0-arm64.img.xz` для Raspberry Pi Imager.
- `HomeTV-Pi-0.3.0-arm64.img.xz.sha256` для проверки скачанного файла и `HomeTV-Pi-0.3.0-arm64.img.sha256` для проверки распакованного образа.
- `HomeTV-Pi-0.3.0-arm64.packages.tsv` со списком пакетов и версий.
- `pcsx-rearmed-<ревизия>.tar.gz` и `retroarch-joypad-autoconfig-<ревизия>.tar.gz` с исходниками ядра PS1 и профилей контроллеров соответственно.
- `os-list.json` и `hometv-icon.svg` для каталога Imager.
- `build.log` с журналом Docker и `pi-gen`.

Для собственного каталога Imager разместите образ, значок и `os-list.json` в HTTPS-хранилище. Адреса внутри манифеста определяются `HOMETV_RELEASE_URL`. По умолчанию это адрес файлов релиза в репозитории SmartTV-Pi. Для локального файла используйте **Use custom** в Imager. Для опубликованного каталога запустите `rpi-imager --repo` с HTTPS-адресом `os-list.json`. [Формат манифеста](https://github.com/raspberrypi/rpi-imager/blob/main/doc/schema-notes.md)

## Проверки

`bash build/ci-check.sh` проверяет синтаксис, конфигурационные файлы и тесты Python. GitHub Actions запускает эти проверки на push и pull request. Ручной запуск **HomeTV Pi** в Actions также создаёт архив с образом и журналом.

Сборщик монтирует разделы итогового образа только для чтения, проверяет соответствие `PARTUUID` в конфигурации загрузки, наличие файлов плат, учётные записи и установку Kodi и Chromium. На x86_64 он исполняет Python из arm64 rootfs через QEMU user mode. Загрузка firmware, HDMI, ввод и воспроизведение входят в аппаратную приёмку. [Протокол приёмки](test-report.md)

Ядро PCSX ReARMed компилируется внутри arm64-системы из закреплённой ревизии. Сборщик проверяет SHA256 исходного архива, архитектуру библиотеки и наличие объектов ARM64 dynarec. Профили `udev` также берутся из закреплённой ревизии с проверкой SHA256. [Исходники PCSX ReARMed](https://github.com/libretro/pcsx_rearmed/tree/0f544ce1d18ac7dd114cb8f5507f01a29d3cd58c) · [Профили контроллеров](https://github.com/libretro/retroarch-joypad-autoconfig/tree/0a675f2e98bd43d2eff088a2dd580797d3a8e89f)
