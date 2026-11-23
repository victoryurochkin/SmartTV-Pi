# Этап 0. Исследование и архитектура

Проверка источников и индексов пакетов выполнена 23 ноября 2026 года. Работа на платах, в том числе загрузка, декодирование, ввод, звук и DRM, имеет статус **[НЕ ПРОВЕРЕНО НА УСТРОЙСТВЕ]**.

## Базовая система

Выбрана Raspberry Pi OS Lite arm64 (Debian 13 Trixie). Официальный образ поддерживает Pi 3B, 3B+ и 4B, а также Pi 5. Пакеты Raspberry Pi для Trixie включают Chromium, Kodi и Widevine для arm64 и armhf. На Pi 3 объём памяти важнее разрядности: начинаем с одной графической сессии, 384 МиБ zram и умеренного числа процессов рендерера. Разницу в RSS и достижимое качество измеряем на Pi 3. [Образы Raspberry Pi OS](https://www.raspberrypi.com/software/operating-systems/) · [Индекс arm64](https://archive.raspberrypi.com/debian/dists/trixie/main/binary-arm64/Packages.gz) · [Индекс armhf](https://archive.raspberrypi.com/debian/dists/trixie/main/binary-armhf/Packages.gz).

Сборка использует зафиксированную ревизию ветки arm64 pi-gen и пакеты подписанных репозиториев ОС. Одинаковый рецепт воспроизводит структуру и конфигурацию образа. Обновляемые индексы APT и метаданные файловых систем влияют на побайтовую идентичность. [pi-gen](https://github.com/RPi-Distro/pi-gen/tree/c0d2c9f2cffc08bc56850b0a3eb23178f4226e8a).

## Графика, декодирование и DRM

| Плата | Цель вывода | Кодеки и проверка |
| --- | --- | --- |
| Pi 3B/3B+ | HDMI до 1080p60 | Документированный ориентир декодера Pi 3B+ — H.264 1080p30. 60 кадров/с проверяем дополнительно. HEVC без аппаратного декодера не входит в профиль. |
| Pi 4B | HDMI до 4K, 4K60 через HDMI0 при подходящем дисплее и кабеле | Спецификация указывает H.264 до 1080p60 и HEVC до 4K60. В Kodi проверяем HEVC Main10 и HDR10. Поддержка HEVC в Chromium и качество DRM требуют отдельной проверки. |
| Pi 5 | Загрузка с безопасными настройками по умолчанию | Вне приёмочной матрицы. H.264 декодируется программно. |

Источники аппаратных возможностей и правил KMS: [спецификация Pi 3B+](https://pip-assets.raspberrypi.com/categories/532-raspberry-pi-3-model-b/documents/RP-008338-DS-2-raspberry-pi-3-b-plus-product-brief.pdf), [Pi 4](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/), [Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/), [параметры прошивки](https://www.raspberrypi.com/documentation/computers/config_txt.html). Имена декодеров Kodi и Chromium нужно снимать отдельно для H.264, HEVC и DRM-видео. Для актуального Chromium Raspberry Pi сопровождающий указывает stateful V4L2 H.264 на моделях до Pi 5. [Kodi DRM PRIME](https://kodi.wiki/view/Settings/Player/Videos) · [Комментарий сопровождающего Chromium](https://forums.raspberrypi.com/viewtopic.php?p=2385322).

На arm64 начиная с Chromium 151 штатный диспетчер компонентов загружает официальный Widevine CDM Google. Обновление компонентов остаётся включено, постоянный профиль сохраняет полученный компонент. Первая загрузка CDM требует интернета и может потребовать повторного открытия сервиса. Извлечённые из других устройств бинарники, ключи и сертификаты в образ не входят. Наличие CDM не определяет качество у конкретного провайдера. [Разъяснение сопровождающего пакета](https://forums.raspberrypi.com/viewtopic.php?t=399940) · [Widevine](https://www.widevine.com/) · [Netflix](https://help.netflix.com/en/node/30081) · [Prime Video](https://www.primevideo.com/help/?nodeId=GUX9FYHU5D8LC9EJ).

## Сессии, хранение и обновления

- Kodi GBM работает на KMS. Chromium Wayland работает в Cage с включённой песочницей. Сессии управляются systemd, разделяют VT и получают команды через локальные интерфейсы. Для Chromium нужен постоянный каталог на каждый сервис. Прерывание браузера освобождает ресурсы DRM и запускает Kodi. [Cage](https://github.com/cage-kiosk/cage) · [systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html).
- Автоопределение платы читает device tree, а ограничения, необходимые до запуска Linux, задаются секциями прошивки `[pi3]` и `[pi4]`. Параметры HDMI выбираются по EDID. Композит требует отдельной проверки режима KMS и конкретного кабеля. [Документация config.txt](https://www.raspberrypi.com/documentation/computers/config_txt.html).
- Поверх корня используется временный OverlayFS. Постоянные данные, профили и экспорт настроек привязаны к отдельному ext4-разделу. Механизм расширения адресует последнюю партицию только после проверки источника загрузки. [OverlayFS](https://docs.kernel.org/filesystems/overlayfs.html).
- Для ОС предпочтительны подписанные полные обновления с отдельной пробной загрузкой. Официальная схема обновления разделов Raspberry Pi Connect требует Pi 4 или новее. Флаг `tryboot` описан для всех моделей, а на ранних ревизиях Pi 4 требуется доступ на запись в EEPROM. Пробный старт и откат на Pi 3 входят в аппаратную приёмку. Пока безопасность этого пути не подтверждена, основной образ сохраняется, а пробную версию записывают на отдельную карту после резервной копии. [Tryboot](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#tryboot) · [Разметка и пробная загрузка](https://www.raspberrypi.com/documentation/computers/config_txt.html#example-update-flow-for-ab-booting) · [Remote updates](https://www.raspberrypi.com/documentation/services/connect.html#remote-updates).

Результаты сервисов ведутся в [матрице совместимости](compat.md), аппаратные сценарии в [протоколе приёмки](test-report.md).
