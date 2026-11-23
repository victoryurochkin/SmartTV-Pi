# Компоненты и источники контента

Каждый компонент распространяется на своих условиях. Для установленных Debian-пакетов тексты лицензий и сведения об авторах хранятся в образе в `/usr/share/doc/<пакет>/copyright`. `*.packages.tsv` рядом с образом перечисляет фактически установленные версии.

| Компонент | Где смотреть условия |
| --- | --- |
| Raspberry Pi OS и прошивка | [Raspberry Pi OS](https://www.raspberrypi.com/software/operating-systems/) · [Лицензия бинарной прошивки](https://github.com/raspberrypi/firmware/blob/master/boot/LICENCE.broadcom) |
| pi-gen | [Лицензия pi-gen](https://github.com/RPi-Distro/pi-gen/blob/arm64/LICENSE) |
| Kodi и языковое дополнение | [Лицензии Kodi](https://github.com/xbmc/xbmc/tree/Omega/LICENSES) · [Официальные дополнения Kodi](https://mirrors.kodi.tv/addons/omega/) |
| Chromium | [Лицензия Chromium](https://chromium.googlesource.com/chromium/src/+/main/LICENSE) и файлы лицензий сторонних компонентов |
| Cage, wlroots, UDisks, PipeWire, BlueZ | Лицензии указаны в метаданных соответствующих пакетов внутри образа |
| Simon Tatham’s Portable Puzzle Collection и LBreakoutHD | [Пакет и исходники головоломок](https://packages.debian.org/trixie/sgt-puzzles) · [Пакет и исходники LBreakoutHD](https://packages.debian.org/trixie/lbreakouthd) |
| RetroArch и Nestopia | [Пакет RetroArch](https://packages.debian.org/trixie/retroarch) · [Nestopia, GPLv2](https://docs.libretro.com/library/nestopia/) |
| Genesis Plus GX | Ядро поставляется из подписанного раздела `non-free` Debian Trixie. Лицензия разрешает некоммерческое использование, поэтому образ с этим ядром предназначен для личного использования. [Пакет Debian](https://packages.debian.org/trixie/libretro-genesisplusgx) · [Условия ядра](https://docs.libretro.com/library/genesis_plus_gx/#authorlicense) |
| PCSX ReARMed | GPLv2. Архив исходников закреплённой ревизии поставляется рядом с образом. [Исходники и лицензия](https://github.com/libretro/pcsx_rearmed/tree/0f544ce1d18ac7dd114cb8f5507f01a29d3cd58c) |
| Профили RetroArch для контроллеров | MIT. Лицензия находится в `/usr/share/doc/home-tv-joypad-autoconfig/COPYING` внутри образа. [Файл лицензии](https://github.com/libretro/retroarch-joypad-autoconfig/blob/0a675f2e98bd43d2eff088a2dd580797d3a8e89f/COPYING) |
| Widevine | [Условия Widevine](https://www.widevine.com/) · компонент загружается штатным Chromium после первого запуска |

Плитки HomeTV Pi обращаются к публичным официальным страницам провайдеров. Оплата, вход, проверка региона и DRM остаются на стороне провайдера. Проект не распространяет контент, ключи, чужие учётные данные или способы обхода DRM. Используйте свои медиа и источники, на которые у вас есть права.
