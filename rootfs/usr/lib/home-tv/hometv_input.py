"""Local virtual keyboard and pointer shared by the browser and phone remote."""

import string
import threading

from evdev import UInput, ecodes


KEY_NAMES = {
    'play_pause': 'KEY_PLAYPAUSE',
    'page_up': 'KEY_PAGEUP',
    'page_down': 'KEY_PAGEDOWN',
    'volume_up': 'KEY_VOLUMEUP',
    'volume_down': 'KEY_VOLUMEDOWN',
    'escape': 'KEY_ESC',
    'back': 'KEY_ESC',
    'ok': 'KEY_ENTER',
    'mode': 'KEY_F9',
}
KEY_CODES = list(range(ecodes.KEY_ESC, ecodes.KEY_F12 + 1)) + [
    ecodes.KEY_HOME, ecodes.KEY_END, ecodes.KEY_UP, ecodes.KEY_DOWN,
    ecodes.KEY_LEFT, ecodes.KEY_RIGHT, ecodes.KEY_PAGEUP, ecodes.KEY_PAGEDOWN,
    ecodes.KEY_INSERT, ecodes.KEY_DELETE, ecodes.KEY_BACK, ecodes.KEY_MUTE,
    ecodes.KEY_VOLUMEDOWN, ecodes.KEY_VOLUMEUP, ecodes.KEY_PLAYPAUSE,
    ecodes.KEY_STOPCD, ecodes.KEY_PREVIOUSSONG, ecodes.KEY_NEXTSONG,
    ecodes.KEY_RIGHTCTRL, ecodes.KEY_RIGHTALT, ecodes.KEY_RIGHTSHIFT,
]


def ascii_keys():
    keys = {
        char: (getattr(ecodes, 'KEY_' + char.upper()), char.isupper())
        for char in string.ascii_letters + string.digits
    }
    punctuation = {
        '-_': 'MINUS', '=+': 'EQUAL', '[{': 'LEFTBRACE', ']}': 'RIGHTBRACE',
        ';:': 'SEMICOLON', '\'"': 'APOSTROPHE', '`~': 'GRAVE', '\\|': 'BACKSLASH',
        ',<': 'COMMA', '.>': 'DOT', '/?': 'SLASH', ' ': 'SPACE',
    }
    for pair, name in punctuation.items():
        for index, char in enumerate(pair):
            keys[char] = getattr(ecodes, 'KEY_' + name), index == 1
    for digit, char in zip('1234567890', '!@#$%^&*()'):
        keys[char] = keys[digit][0], True
    return keys


ASCII_KEYS = ascii_keys()


class InputDevice:
    def __init__(self, name='HomeTV Phone'):
        self.lock = threading.RLock()
        self.keyboard = UInput({ecodes.EV_KEY: sorted(set(KEY_CODES))}, name=f'{name} keyboard')
        try:
            self.pointer = UInput({
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
            }, name=f'{name} pointer')
        except Exception:
            self.keyboard.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        with self.lock:
            self.pointer.close()
            self.keyboard.close()

    def key(self, name):
        default_name = 'KEY_' + name.upper().removeprefix('KEY_')
        code = ecodes.ecodes.get(KEY_NAMES.get(name.lower(), default_name))
        if code not in KEY_CODES:
            raise ValueError('Эта клавиша недоступна')
        self.key_code(code)

    def key_code(self, code):
        with self.lock:
            self.keyboard.write(ecodes.EV_KEY, code, 1)
            self.keyboard.syn()
            self.keyboard.write(ecodes.EV_KEY, code, 0)
            self.keyboard.syn()

    def move(self, dx, dy):
        if not all(type(delta) is int and -1024 <= delta <= 1024 for delta in (dx, dy)):
            raise ValueError('Смещение курсора должно быть целым числом от −1024 до 1024')
        with self.lock:
            self.pointer.write(ecodes.EV_REL, ecodes.REL_X, dx)
            self.pointer.write(ecodes.EV_REL, ecodes.REL_Y, dy)
            self.pointer.syn()

    def click(self, button='left'):
        buttons = {'left': ecodes.BTN_LEFT, 'right': ecodes.BTN_RIGHT}
        if button not in buttons:
            raise ValueError('Неизвестная кнопка мыши')
        with self.lock:
            self.pointer.write(ecodes.EV_KEY, buttons[button], 1)
            self.pointer.syn()
            self.pointer.write(ecodes.EV_KEY, buttons[button], 0)
            self.pointer.syn()

    def type_text(self, text):
        if not isinstance(text, str) or len(text) > 256 or any(char not in ASCII_KEYS for char in text):
            raise ValueError('Введите до 256 печатных символов английской раскладки')
        with self.lock:
            for char in text:
                code, shift = ASCII_KEYS[char]
                if shift:
                    self.keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                    self.keyboard.syn()
                try:
                    self.key_code(code)
                finally:
                    if shift:
                        self.keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                        self.keyboard.syn()
