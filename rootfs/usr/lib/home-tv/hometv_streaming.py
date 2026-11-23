"""Validate the streaming catalogue before passing values to Chromium."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_CATALOGUE = Path('/usr/share/home-tv/services.json')
USER_CATALOGUE = Path('/data/config/services.json')
SERVICE_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,39}\Z')
ALLOWED_FLAGS = {
    'spatial-navigation': '--enable-spatial-navigation',
    'autoplay': '--autoplay-policy=no-user-gesture-required',
}


def validate_service_id(value):
    return isinstance(value, str) and SERVICE_ID.fullmatch(value) is not None


def text_field(value, limit):
    return (
        isinstance(value, str)
        and len(value) <= limit
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def validate_catalogue(catalogue):
    services = catalogue.get('services') if isinstance(catalogue, dict) else None
    if not isinstance(services, list) or len(services) > 100:
        raise ValueError('Каталог должен содержать список services из 0–100 записей')

    by_id = {}
    for service in services:
        if not isinstance(service, dict) or not validate_service_id(service.get('id')):
            raise ValueError('Некорректный идентификатор сервиса')
        service_id = service['id']
        if service_id in by_id:
            raise ValueError(f'Повторяющийся идентификатор сервиса: {service_id}')

        name = service.get('name')
        if not text_field(name, 80) or not name.strip():
            raise ValueError(f'Некорректное название сервиса: {service_id}')
        url = service.get('url')
        if not text_field(url, 2048) or any(char.isspace() for char in url) or '\\' in url:
            raise ValueError(f'Некорректный URL сервиса: {service_id}')
        address = urlsplit(url)
        if address.scheme != 'https' or not address.hostname or '@' in address.netloc:
            raise ValueError(f'Нужен HTTPS URL без логина и пароля: {service_id}')
        if address.port == 0:
            raise ValueError(f'Некорректный порт сервиса: {service_id}')

        for key, limit in {'icon': 512, 'quality_note': 240}.items():
            if not text_field(service.get(key, ''), limit):
                raise ValueError(f'Некорректное поле {key}: {service_id}')
        user_agent = service.get('user_agent')
        if user_agent is not None and (not text_field(user_agent, 512) or not user_agent.isascii()):
            raise ValueError(f'Некорректный User-Agent: {service_id}')
        flags = service.get('flags', [])
        if not isinstance(flags, list) or any(
            not isinstance(flag, str) or flag not in ALLOWED_FLAGS for flag in flags
        ):
            raise ValueError(f'Неизвестный параметр браузера: {service_id}')
        zoom = service.get('zoom', 1.0)
        if type(zoom) not in (int, float) or not 0.5 <= zoom <= 3.0:
            raise ValueError(f'Масштаб должен быть числом от 0.5 до 3.0: {service_id}')
        if not isinstance(service.get('prefer_h264', False), bool):
            raise ValueError(f'Некорректное поле prefer_h264: {service_id}')
        by_id[service_id] = service
    return by_id


def load_catalogue(default_path=DEFAULT_CATALOGUE, user_path=USER_CATALOGUE):
    try:
        with user_path.open(encoding='utf-8') as stream:
            return validate_catalogue(json.load(stream))
    except FileNotFoundError:
        with default_path.open(encoding='utf-8') as stream:
            return validate_catalogue(json.load(stream))
