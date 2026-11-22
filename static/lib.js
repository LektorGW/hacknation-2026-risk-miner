const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  file: '<path d="M14 2H5v20h14V7l-5-5zm0 0v6h5M8 13h8M8 17h6"/>',
  verify: '<path d="m12 2 8 3v6c0 5-3 8-8 11-5-3-8-6-8-11V5zm-4 10 3 3 5-6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l3 2"/>',
  replay: '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l4 2"/>',
  analysis: '<path d="M3 3v18h18M7 16l4-6 4 3 6-8"/>',
  arrows: '<path d="m9 6-6 6 6 6m6-12 6 6-6 6"/>',
  settings:
    '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor"/><circle cx="15" cy="12" r="2" fill="currentColor"/><circle cx="8" cy="18" r="2" fill="currentColor"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M3 15v5h18v-5"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M3 16v5h18v-5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  right: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  next: '<path d="m9 5 7 7-7 7"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  water: '<path d="M12 2s-7 8-7 13a7 7 0 0 0 14 0c0-5-7-13-7-13Zm-3 14a3 3 0 0 0 3 3"/>',
  flag: '<path d="M5 22V3c5-3 9 3 15 0v10c-6 3-10-3-15 0"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',
  edit: '<path d="m14 5 5 5M3 21l5-1L21 7l-5-5L3 15z"/>',
  link: '<path d="m10 14 4-4m-5-1 4-4a5 5 0 0 1 7 7l-4 4m-1-1-4 4a5 5 0 1 1-7-7l4-4"/>',
  book: '<path d="M3 4c4-1 7 0 9 2 3-2 6-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2zm9 2v15"/>',
  note: '<path d="M5 3h14v18H5zM8 7h8M8 11h8m-8 4h5"/>',
  checkfile: '<path d="M14 2H4v20h16V8zm0 0v6h6m-12 7 3 3 5-7"/>',
  folder: '<path d="M3 6h7l2 2h9v12H3z"/>',
  external: '<path d="M13 3h8v8m0-8L10 14m0-10H3v17h17v-7"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18"/>',
  refresh: '<path d="M20 9a8 8 0 0 0-14-3L3 9m0-6v6h6m-5 6a8 8 0 0 0 14 3l3-3m0 6v-6h-6"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  pin: '<path d="M19 9c0 5-7 12-7 12S5 14 5 9a7 7 0 0 1 14 0Z"/><circle cx="12" cy="9" r="2"/>',
};
export function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
}
export function esc(v) {
  return String(v ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
}
export const arr = (v) => (Array.isArray(v) ? v : []);
export const store = {
  projects: [],
  reviews: [],
  catalog: [],
  audit: [],
  stats: {},
  auth: { role: 'viewer' },
  loaded: false,
};
export const writable = () => ['admin', 'expert'].includes(store.auth?.role);
export const projectURL = (id) => '#projekt/' + encodeURIComponent(String(id));
export const apiURL = (id) => '/api/projects/' + encodeURIComponent(String(id));
export const num = (v, p = 1) =>
  v === undefined || v === null || v === '' || !Number.isFinite(Number(v))
    ? '—'
    : Number(v).toLocaleString('pl-PL', { maximumFractionDigits: p });
export const money = (v) => (v === undefined || v === null || v === '' ? '—' : num(v, 2) + ' zł');
export function date(v) {
  if (typeof v !== 'string' || !/^\d{4}-\d\d-\d\d/.test(v)) return '—';
  const dt = new Date(v.slice(0, 10) + 'T12:00:00Z');
  return Number.isFinite(dt.getTime())
    ? new Intl.DateTimeFormat('pl-PL', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      }).format(dt)
    : '—';
}
export const text = (v, empty = '—') => (typeof v === 'string' || typeof v === 'number' ? esc(v) || empty : empty);
export const currProject = (id) => store.projects.find((p) => String(p.id) === String(id));
export const labels = {
  planned: 'Planowana',
  active: 'W realizacji',
  completed: 'Zakończona',
  pending: 'Do weryfikacji',
  accepted: 'Zatwierdzono',
  approved: 'Zatwierdzono',
  corrected: 'Skorygowano',
  rejected: 'Odrzucono',
  demo: 'Dane demonstracyjne',
  public: 'Dane publiczne',
  user: 'Dane użytkownika',
  proposal: 'Propozycja',
  open: 'Do wyjaśnienia',
  partial: 'Częściowo wyjaśnione',
  documented: 'Udokumentowane',
  expert: 'Ekspert',
  admin: 'Administrator',
  viewer: 'Odczyt',
  link: 'Powiązanie',
  event: 'Zdarzenie',
  finding: 'Wniosek',
  match: 'Dopasowanie',
  category: 'Kategoria',
  conclusion: 'Wniosek',
  proposed: 'Propozycja',
  unknown: 'Nieustalony',
  verified: 'Zweryfikowano',
  observation: 'Obserwacja',
  document: 'Dokument',
  evidence: 'Dowód',
};
export const label = (v) => labels[v] || v || 'Brak oznaczenia';
export function pill(v) {
  if (!v) return '';
  const tone =
    {
      demo: 'mauve',
      pending: 'warning',
      open: 'warning',
      partial: 'warning',
      proposal: 'warning',
      proposed: 'warning',
      accepted: 'positive',
      approved: 'positive',
      active: 'blue',
      completed: 'positive',
      public: 'blue',
      documented: 'positive',
      corrected: 'positive',
    }[v] || '';
  return `<span class="pill ${tone}"><span class="dot"></span>${esc(label(v))}</span>`;
}
export function pagehead(title, description = '', buttons = '') {
  return `<div class="pagehead"><div><h1>${esc(title)}</h1>${description ? `<p>${esc(description)}</p>` : ''}</div>${buttons ? `<div class="actions">${buttons}</div>` : ''}</div>`;
}
export function notice(content, warning = false) {
  return `<div class="notice ${warning ? 'warning' : ''}">${icon('info')}<p>${esc(content)}</p></div>`;
}
export function linkBtn(href, title, ico = '', style = '') {
  return `<a class="button ${style}" href="${esc(href)}">${ico ? icon(ico) : ''}${esc(title)}</a>`;
}
export function empty(s) {
  return `<p class="empty">${esc(s)}</p>`;
}
export const field = (title, inner) => `<label class="field">${esc(title)}${inner}</label>`;
export function selectOptions(items, chosen) {
  return items
    .map(
      ([v, t]) =>
        `<option value="${esc(v)}" ${String(chosen ?? '') === String(v) ? 'selected' : ''}>${esc(t)}</option>`
    )
    .join('');
}
export function recordDetails(value) {
  return `<details><summary>Wszystkie pola rekordu</summary><pre>${esc(JSON.stringify(value, null, 2))}</pre></details>`;
}
export function safeLink(v) {
  try {
    const u = new URL(v);
    if (u.protocol === 'https:' || u.protocol === 'http:') return esc(u.href);
  } catch {}
  return '';
}
export function source(ref, project) {
  const d = typeof ref === 'string' ? { id: ref } : ref || {};
  const full = arr(project?.documents).find((x) => x.id === (d.source_id || d.id)) || {};
  const obj = { ...full, ...d },
    path = obj.url || obj.source_url || '',
    url = safeLink(path);
  const quote = obj.excerpt || obj.quote || obj.text || '',
    name = obj.title || obj.source || obj.id || 'Źródło';
  const local = /^\/api\/(?:files|knowledge)\/[\w.-]+$/.test(path);
  return `<details class="source"><summary>${icon('file')} ${esc(name)}${obj.locator ? ' · ' + esc(obj.locator) : ''}</summary><div class="sub">${[obj.source, obj.published_at ? 'Publikacja ' + date(obj.published_at) : '', obj.retrieved_at ? 'Pobrano ' + date(obj.retrieved_at) : ''].filter(Boolean).map(esc).join(' · ')}</div>${quote ? `<blockquote>${esc(quote)}</blockquote>` : ''}${local ? `<button class="text-button" data-act="local-source" data-path="${esc(path)}" data-name="${esc(name)}">${icon('file')} ${path.startsWith('/api/files/') ? 'Pobierz dokument' : 'Otwórz fragment źródłowy'}</button>` : url ? `<a href="${url}" target="_blank" rel="noopener noreferrer">Otwórz źródło ${icon('external')}</a>` : ''}</details>`;
}
export function evidence(list, project) {
  return arr(list)
    .map((x) => source(x, project))
    .join('');
}
export function projectRow(p) {
  return `<a class="project-row" href="${projectURL(p.id)}"><span class="icon-tile">${icon('water')}</span><span class="grow"><span class="title">${text(p.title)}</span><span class="sub">${[p.location || p.buyer, label(p.dataset)].filter(Boolean).map(esc).join(' · ')}</span></span>${pill(p.status)}${icon('next')}</a>`;
}
export async function request(path, options = {}) {
  const token = sessionStorage.getItem('riskminer-access');
  const headers = { ...options.headers };
  if (token) headers.Authorization = 'Bearer ' + token;
  const init = { ...options, headers };
  if (init.body && !(init.body instanceof FormData) && typeof init.body !== 'string') {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(init.body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error('Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.');
  }
  if (!res.ok) {
    let payload;
    try {
      payload = await res.json();
    } catch {}
    const detail = payload?.detail ?? payload?.error;
    const msg =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((e) => e.msg)
              .filter(Boolean)
              .join(', ')
          : '';
    const e = new Error(msg || `Serwer zwrócił błąd HTTP ${res.status}.`);
    e.status = res.status;
    throw e;
  }
  return res;
}
export async function api(path, options) {
  const res = await request(path, options);
  return res.status === 204 ? {} : res.json();
}
export async function sync() {
  const state = await api('/api/state');
  Object.assign(store, state, { loaded: true });
}
export async function saveBlob(data, name, type = 'application/json') {
  const blob =
    data instanceof Blob
      ? data
      : new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], { type });
  const url = URL.createObjectURL(blob),
    a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
export function toast(message) {
  const el = document.querySelector('#toast');
  el.textContent = message;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    el.textContent = '';
  }, 4300);
}
export function dialog(title, content) {
  const el = document.querySelector('#modal');
  document.querySelector('#modal-content').innerHTML =
    `<div class="modal-head"><h2 id="modal-title">${esc(title)}</h2><button class="ghost square" data-act="close" aria-label="Zamknij">${icon('close')}</button></div>${content}`;
  if (!el.open) el.showModal();
  requestAnimationFrame(() => {
    const f = el.querySelector('[autofocus]');
    if (f) f.focus();
  });
}
export function closeDialog() {
  document.querySelector('#modal').close();
}
export async function submitTask(form, fn) {
  const controls = [...form.querySelectorAll('button[type=submit], button:not([type]), input[type=submit]')],
    out = form.querySelector('[role=status]');
  if (form.dataset.busy === 'true') return;
  form.dataset.busy = 'true';
  form.setAttribute('aria-busy', 'true');
  controls.forEach((x) => (x.disabled = true));
  if (out) {
    out.textContent = 'Trwa przetwarzanie…';
    out.classList.remove('error');
  }
  try {
    await fn();
    if (out?.isConnected && out.textContent === 'Trwa przetwarzanie…') out.textContent = 'Gotowe.';
  } catch (e) {
    if (out) {
      out.textContent = e.message;
      out.classList.add('error');
    } else toast(e.message);
  } finally {
    form.dataset.busy = 'false';
    form.removeAttribute('aria-busy');
    controls.forEach((x) => (x.disabled = false));
  }
}
export const statusLine = '<p class="status-message" role="status"></p>';
