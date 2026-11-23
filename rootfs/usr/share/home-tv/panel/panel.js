const find = (id) => document.getElementById(id);
const say = (message) => { find('message').textContent = message; };

async function api(path, data) {
  const options = data === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  };
  const response = await fetch(`/api/${path}`, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

function perform(action) {
  return Promise.resolve().then(action).catch((error) => say(error.message || 'Нет связи с приставкой'));
}

function form(id, action) {
  find(id).addEventListener('submit', (event) => {
    event.preventDefault();
    perform(() => action(event.currentTarget || find(id), event.submitter));
  });
}

let deviceStatus;
async function showStatus() {
  deviceStatus = await api('status');
  const { version, temperature, memory, load, network, throttle, units, failures } = deviceStatus;
  find('device').textContent = `${version} · ${temperature === null ? '—' : `${temperature} °C`}`;
  find('status').textContent = [
    `Память: ${memory.MemAvailable} из ${memory.MemTotal} МиБ свободно`,
    `Нагрузка: ${load.map((item) => item.toFixed(2)).join(' / ')}`,
    `Сеть: ${network.join(', ')}`,
    `Троттлинг: ${throttle ?? 'нет данных'}`,
    ...Object.entries(units).map(([unit, state]) => `${unit}: ${state}`),
    ...Object.entries(failures).map(([unit, failure]) => `${unit}: ${failure.result} (${failure.code})`),
  ].join('\n');
}

async function showControls() {
  find('login').hidden = true;
  find('controls').hidden = false;
  say('');
  const [catalogue, parental] = await Promise.all([api('services'), api('parental'), showStatus()]);
  find('services').elements.catalogue.value = JSON.stringify(catalogue, null, 2);
  find('parental').elements.locked.value = parental.locked.join(' ');
}

form('login', async (element) => {
  await api('login', { pin: element.elements.pin.value });
  element.reset();
  await showControls();
});

document.querySelectorAll('[data-key], [data-action]').forEach((button) => {
  button.addEventListener('click', () => perform(() => api('remote', {
    action: button.dataset.action || 'key', key: button.dataset.key,
  })));
});

form('keyboard', async (element) => {
  const text = element.elements.text.value;
  element.reset();
  await api('remote', { action: 'text', text });
});

let pointer = null;
let pending = null;
let moving = false;
const touchpad = find('touchpad');
touchpad.addEventListener('pointerdown', (event) => {
  pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, travelled: 0 };
  touchpad.setPointerCapture(pointer.id);
});

async function sendMotion() {
  if (!pending || moving) return;
  const { x, y } = pending;
  pending = null;
  moving = true;
  try {
    await api('remote', { action: 'move', x, y });
  } catch (error) {
    say(error.message);
    pending = null;
  } finally {
    moving = false;
  }
  sendMotion();
}

touchpad.addEventListener('pointermove', (event) => {
  if (pointer?.id !== event.pointerId) return;
  const x = Math.round(event.clientX - pointer.x);
  const y = Math.round(event.clientY - pointer.y);
  if (!x && !y) return;
  pointer = { id: pointer.id, x: event.clientX, y: event.clientY, travelled: pointer.travelled + Math.abs(x) + Math.abs(y) };
  const clamp = (value) => Math.max(-250, Math.min(250, value));
  pending = { x: clamp(x + (pending?.x || 0)), y: clamp(y + (pending?.y || 0)) };
  sendMotion();
});
touchpad.addEventListener('pointerup', (event) => {
  if (pointer?.id !== event.pointerId) return;
  if (pointer.travelled < 5) perform(() => api('remote', { action: 'click' }));
  pointer = null;
});
touchpad.addEventListener('pointercancel', () => { pointer = null; });

find('refresh').addEventListener('click', () => perform(showStatus));
find('diagnostic').addEventListener('click', () => perform(async () => {
  const link = document.createElement('a');
  link.href = '/api/diagnostics';
  link.download = 'hometv-diagnostics.zip';
  link.click();
}));

form('services', async (element) => {
  await api('services', JSON.parse(element.elements.catalogue.value));
  say('Каталог сохранён. Откройте главный экран заново.');
});

form('new-service', async (element) => {
  const catalogue = await api('services');
  const { label, url } = element.elements;
  const id = `custom-${crypto.getRandomValues(new Uint32Array(1))[0].toString(16)}`;
  catalogue.services.push({ id, name: label.value, url: url.value });
  await api('services', catalogue);
  find('services').elements.catalogue.value = JSON.stringify(catalogue, null, 2);
  element.reset();
  say(`Плитка добавлена (${id}).`);
});

form('parental', async (element) => {
  const value = element.elements.locked.value.trim();
  await api('parental', { locked: value ? value.split(/\s+/) : [] });
  say('Защита плиток сохранена.');
});

find('scan').addEventListener('click', () => perform(async () => {
  const networks = await api('admin', { action: 'wifi-scan' });
  find('networks').replaceChildren(...networks.map(({ ssid }) => new Option(ssid, ssid)));
  say('Список сетей обновлён.');
}));

form('wifi', async (element) => {
  const { ssid, password, hidden } = element.elements;
  const data = { action: 'wifi-connect', ssid: ssid.value, password: password.value, hidden: hidden.checked };
  password.value = '';
  await api('admin', data);
  say('Wi-Fi подключён.');
});

form('ssh', async (element) => {
  await api('admin', { action: 'ssh-configure', enabled: true, key: element.elements.key.value.trim() });
  element.reset();
  say('SSH включён. Пользователь tvadmin.');
});
find('ssh-off').addEventListener('click', () => perform(async () => {
  await api('admin', { action: 'ssh-configure', enabled: false });
  say('SSH выключен.');
}));

find('drives').addEventListener('click', () => perform(async () => {
  const drives = await api('usb');
  find('backup').elements.device.replaceChildren(...drives.map(({ device, label }) => new Option(label, device)));
  find('backup').elements.file.replaceChildren();
}));
form('backup', async (element, button) => {
  const action = button.value;
  const { device, file } = element.elements;
  if (action === 'restore' && (!file.value || !confirm('Восстановить настройки из выбранного архива?'))) return;
  const result = await api('backup', { action, device: device.value, file: file.value });
  if (action === 'list') file.replaceChildren(...result.files.map((name) => new Option(name, name)));
  if (action === 'export') say(`Записано на USB: ${result.file}`);
  if (action === 'restore') say('Настройки восстановлены. Переоткройте главный экран.');
});
