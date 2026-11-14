const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

// Exercise the actual page script with a minimal DOM and controlled network.
async function boot(fetch, microphone = true) {
  const nodes = new Map();
  function node() {
    return {
      value: '', children: [], listeners: {}, textContent: '', disabled: false,
      classList: { toggle() {}, add() {}, remove() {} },
      append(...items) { this.children.push(...items); },
      replaceChildren(...items) { this.children = items; },
      setAttribute() {},
      addEventListener(name, fn) { this.listeners[name] = fn; },
    };
  }
  const document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); },
    createElement: node, createElementNS: node, createTextNode: (text) => text,
  };
  const context = vm.createContext({
    document, fetch, AbortSignal, setTimeout, clearTimeout,
    navigator: microphone ? { mediaDevices: { getUserMedia() {} } } : {},
  });
  await vm.runInContext(`(async () => { ${source} })()`, context);
  return (id) => document.getElementById(id);
}

const vehicle = { id: 'TEST', brand: 'Auto', model: 'Demo', body: 'suv', price_usd: 12000, year: 2020, km: 1000, features: ['automatico'] };
const ok = (data) => ({ ok: true, json: async () => data });
const config = { voice_enabled: true, max_duration_seconds: 180 };

test('catalog survives an unavailable voice service', async () => {
  const $ = await boot(async (url) => url === '/api/catalog' ? ok({ vehicles: [vehicle] }) : { ok: false, status: 503 });
  assert.equal($('catalog-count').textContent, '1 autos ficticios');
  assert.equal($('vehicles').children.length, 1);
  assert.equal($('start').disabled, true);
  assert.match($('voice-status').textContent, /No pudimos comprobar/);
});

test('catalog failure preserves voice and can be retried without reloading', async () => {
  let attempts = 0;
  const $ = await boot(async (url) => {
    if (url === '/api/config') return ok(config);
    if (++attempts === 1) throw new Error('offline');
    return ok({ vehicles: [vehicle] });
  });
  assert.equal($('start').disabled, false);
  const retry = $('vehicles').children[1];
  $('filters').listeners.input();
  assert.equal($('vehicles').children[1], retry);
  retry.listeners.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(attempts, 2);
  assert.equal($('catalog-count').textContent, '1 autos ficticios');
});

test('unsupported microphone explains the requirement and blocks starting', async () => {
  let calls = 0;
  const $ = await boot(async (url) => {
    calls++;
    return ok(url === '/api/config' ? config : { vehicles: [] });
  }, false);
  assert.equal($('start').disabled, true);
  assert.match($('voice-status').textContent, /HTTPS o localhost/);
  await $('voice-form').listeners.submit({ preventDefault() {} });
  assert.equal(calls, 2);
});

test('every startup request has a timeout and empty results remain filterable', async () => {
  const $ = await boot(async (url, options) => {
    assert.ok(options.signal instanceof AbortSignal);
    return ok(url === '/api/config' ? { ...config, voice_enabled: false } : { vehicles: [vehicle] });
  });
  $('budget').value = '1';
  $('filters').listeners.input();
  assert.equal($('catalog-count').textContent, '0 autos ficticios');
  assert.match($('vehicles').children[0].textContent, /No hay autos/);
  assert.equal($('start').disabled, true);
});
