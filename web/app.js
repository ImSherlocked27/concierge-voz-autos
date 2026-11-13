const $ = (id) => document.getElementById(id);
const format = new Intl.NumberFormat('es-AR');
const labels = { automatico: 'Automático', manual: 'Manual', camara: 'Cámara', isofix: 'ISOFIX', diesel: 'Diésel' };
let catalog = [];
let conversation = null;
let timer = null;
let connecting = false;
let duration = 180;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function carArt(body) {
  // Original schematic illustration, deliberately not a photograph of the listed model.
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 300 120');
  svg.setAttribute('aria-hidden', 'true');
  const tall = body === 'suv' || body === 'pickup';
  const shapes = [
    ['path', { d: tall ? 'M30 78 L38 56 L73 50 L100 22 L194 22 L223 51 L265 58 L277 78 L273 92 L28 92 Z' : 'M26 79 L37 62 L82 53 L116 29 L187 29 L220 54 L264 62 L276 80 L271 92 L28 92 Z', fill: 'currentColor' }],
    ['path', { d: tall ? 'M91 49 L111 30 L146 30 L146 49 Z M154 30 L188 30 L209 49 L154 49 Z' : 'M96 52 L121 36 L146 36 L146 52 Z M154 36 L182 36 L206 52 L154 52 Z', fill: '#dce6dc' }],
    ['path', { d: 'M38 73 H65 M236 72 H264 M146 59 H158 M171 65 H181', stroke: '#b7c6b2', 'stroke-width': '3', 'stroke-linecap': 'round' }],
    ['circle', { cx: '78', cy: '91', r: '18', fill: '#283b32' }],
    ['circle', { cx: '230', cy: '91', r: '18', fill: '#283b32' }],
    ['circle', { cx: '78', cy: '91', r: '9', fill: '#c7d1c3' }],
    ['circle', { cx: '230', cy: '91', r: '9', fill: '#c7d1c3' }],
  ];
  for (const [tag, attributes] of shapes) {
    const shape = document.createElementNS(svg.namespaceURI, tag);
    for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
    svg.append(shape);
  }
  return svg;
}

function renderCatalog() {
  const body = $('body').value;
  const rawBudget = $('budget').value;
  const budget = rawBudget === '' ? Infinity : Number(rawBudget);
  const feature = $('feature').value;
  const matches = catalog.filter((v) => (!body || v.body === body) && v.price_usd <= budget && (!feature || v.features.includes(feature)));
  $('vehicles').replaceChildren();
  $('catalog-count').textContent = `${matches.length} autos ficticios`;
  if (!matches.length) $('vehicles').append(element('p', 'empty', 'No hay autos que coincidan. Probá cambiando un filtro.'));
  for (const vehicle of matches) {
    const card = element('article', 'vehicle-card');
    const art = element('div', 'vehicle-art');
    art.append(element('span', 'body-tag', vehicle.body), carArt(vehicle.body));
    const info = element('div', 'vehicle-info');
    const title = element('div', 'vehicle-title');
    title.append(element('h3', '', `${vehicle.brand} ${vehicle.model}`), element('span', 'vehicle-id', vehicle.id));
    const price = element('p', 'vehicle-price', `US$ ${format.format(vehicle.price_usd)}`);
    price.append(element('small', '', 'precio ficticio'));
    const features = element('div', 'features');
    vehicle.features.forEach((f) => features.append(element('span', '', labels[f] || f)));
    info.append(title, element('p', 'vehicle-detail', `${vehicle.year} · ${format.format(vehicle.km)} km`), price, features);
    card.append(art, info);
    $('vehicles').append(card);
  }
}

function status(message, error = false) {
  $('voice-status').textContent = message;
  $('voice-status').classList.toggle('error', error);
}

function disconnected() {
  clearTimeout(timer);
  conversation = null;
  connecting = false;
  $('orb').classList.remove('active');
  $('connection').textContent = 'En espera';
  $('voice-form').hidden = false;
  $('stop').hidden = true;
  $('start').disabled = false;
}

async function stop() {
  if (conversation) await conversation.endSession();
  disconnected();
  status('Conversación terminada. Gracias por probar la demo.');
}

$('voice-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (connecting || conversation) return;
  connecting = true;
  $('start').disabled = true;
  status('Preparando el micrófono y conectando con ElevenLabs…');
  try {
    // Request permission before reserving a quota-limited paid session.
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    const { Conversation } = await import('https://esm.sh/@elevenlabs/client@1.36.1');
    const response = await fetch('/api/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ access_code: $('access-code').value }) });
    const data = await response.json();
    if (!response.ok) throw new Error(response.status === 401 ? 'El código de acceso no es válido.' : response.status === 429 ? 'Llegamos al límite diario de voz. Podés explorar el catálogo.' : 'No se pudo iniciar la voz. Probá nuevamente más tarde.');
    $('transcript').replaceChildren();
    $('transcript-section').hidden = false;
    conversation = await Conversation.startSession({
      signedUrl: data.signed_url,
      connectionType: 'websocket',
      onConnect() {
        $('orb').classList.add('active');
        $('connection').textContent = 'En conversación';
        $('voice-form').hidden = true;
        $('stop').hidden = false;
        status('Te escucho. Podés interrumpirme cuando quieras.');
      },
      onMessage(message) {
        if (!message.message) return;
        const item = element('li');
        item.append(element('strong', '', message.source === 'user' ? 'Vos' : 'Concierge'), document.createTextNode(message.message));
        $('transcript').append(item);
      },
      onDisconnect() { disconnected(); status('La conversación terminó.'); },
      onError() { status('Se interrumpió la conexión de voz. Podés volver a intentar.', true); },
    });
    connecting = false;
    timer = setTimeout(() => stop().catch(() => disconnected()), duration * 1000);
  } catch (error) {
    disconnected();
    status(error.name === 'NotAllowedError' ? 'Necesitamos permiso para usar el micrófono. Podés seguir explorando el catálogo.' : error.message || 'No se pudo conectar con ElevenLabs.', true);
  }
});

$('stop').addEventListener('click', () => stop().catch(() => disconnected()));
$('filters').addEventListener('submit', (event) => event.preventDefault());
$('filters').addEventListener('input', renderCatalog);
$('clear-filters').addEventListener('click', () => { $('filters').reset(); renderCatalog(); });

try {
  const [catalogResponse, configResponse] = await Promise.all([fetch('/api/catalog'), fetch('/api/config')]);
  if (!catalogResponse.ok || !configResponse.ok) throw new Error('No se pudo cargar la demo.');
  catalog = (await catalogResponse.json()).vehicles;
  const config = await configResponse.json();
  duration = config.max_duration_seconds;
  renderCatalog();
  $('start').disabled = !config.voice_enabled;
  if (config.voice_enabled) status('Ingresá el código del autor para probar la voz.');
  else status('La voz está pendiente de configuración. El catálogo ya se puede explorar.');
} catch (error) {
  status(error.message, true);
  $('vehicles').append(element('p', 'empty', 'No pudimos cargar el catálogo. Recargá la página para intentar de nuevo.'));
}
