import {
  api,
  apiURL,
  arr,
  closeDialog,
  currProject,
  dialog,
  empty,
  esc,
  field,
  icon,
  label,
  linkBtn,
  notice,
  num,
  pagehead,
  projectRow,
  projectURL,
  request,
  saveBlob,
  source,
  statusLine,
  store,
  submitTask,
  sync,
  text,
  toast,
} from './lib.js';
import {
  analysisView,
  clearAnalysis,
  handleAnalysisAction,
  handleAnalysisChange,
  handleAnalysisSubmit,
  handleDraftInput,
  restoreAnalysis,
} from './analysis.js';
import {
  auditView,
  catalogView,
  handleExpertAction,
  handleExpertChange,
  handleExpertSubmit,
  importView,
  resetExperts,
  reviewView,
} from './expert.js';
import { caseDetail, caseList, handleCaseAction, handleCaseInput, handleCaseSubmit, matches } from './cases.js';

const groups = [
  [
    'Przestrzeń robocza',
    [
      ['pulpit', 'grid', 'Pulpit'],
      ['baza', 'layers', 'Baza inwestycji'],
      ['ekspert', 'verify', 'Panel eksperta'],
    ],
  ],
  [
    'Analiza',
    [
      ['analiza', 'analysis', 'Nowa analiza'],
      ['proba', 'replay', 'Próba generalna'],
    ],
  ],
  [
    'Zarządzanie',
    [
      ['import', 'upload', 'Import danych'],
      ['katalog', 'book', 'Katalog ekspercki'],
      ['historia', 'clock', 'Historia operacji'],
    ],
  ],
];
const titles = Object.fromEntries(groups.flatMap((g) => g[1].map(([k, i, t]) => [k, t])));
titles.projekt = 'Karta inwestycji';
const main = document.querySelector('#main');
const active = () => {
  try {
    return (location.hash.slice(1) || 'pulpit').split('/').map(decodeURIComponent);
  } catch {
    return ['pulpit'];
  }
};
const sidebar = document.querySelector('#sidebar');
function menu(open) {
  document.body.classList.toggle('menu-open', open);
  sidebar.inert = window.matchMedia('(max-width:720px)').matches && !open;
  document.querySelector('.workspace').inert = open;
  document.querySelector('.mobile-menu').setAttribute('aria-expanded', String(open));
  if (open) sidebar.querySelector('.active')?.focus();
}
function chrome(view) {
  document.querySelector('#nav').innerHTML = groups
    .map(
      ([head, links]) =>
        `<div class="nav-section"><div class="nav-caption">${head}</div>${links.map(([k, i, t]) => `<a class="nav-item ${k === (view === 'projekt' ? 'baza' : view) ? 'active' : ''}" href="#${k}" ${k === (view === 'projekt' ? 'baza' : view) ? 'aria-current="page"' : ''}>${icon(i)}<span>${t}</span>${k === 'ekspert' && store.stats.pending ? `<span class="badge-count">${num(store.stats.pending, 0)}</span>` : ''}</a>`).join('')}</div>`
    )
    .join('');
  const role = label(store.auth?.role),
    actor = store.auth?.actor;
  document.querySelector('#account').innerHTML =
    `<button class="account" data-act="account"><span class="avatar">${icon('user')}</span><span><b>${text(actor || 'Dostęp do aplikacji')}</b><small>${store.loaded ? esc(role) : 'Sesja'}</small></span>${icon('settings')}</button>`;
  document.querySelector('#breadcrumb').textContent = titles[view] || 'Widok';
  document.title = (titles[view] || 'Pulpit') + ' · Risk Miner';
}
function stat(title, value, href, i, tone = '') {
  return `<a class="stat" href="${href}"><small>${esc(title)}</small><strong>${num(value ?? 0, 0)}</strong><span class="icon-tile ${tone}">${icon(i)}</span></a>`;
}
function evidenceSpotlight({ p, c }) {
  const days = c.field === 'planned_days';
  const variants = arr(c.variants);
  const readings = variants.filter((v, i) => variants.findIndex((other) => other.value === v.value) === i);
  return `<section class="evidence-spot" aria-labelledby="evidence-title">
    <div class="spot-meta"><span>${icon('flag')} Rozbieżność źródeł</span><span>${text(p.location || p.buyer)}</span></div>
    <h2 id="evidence-title">${days ? 'Ile dni przewidywała umowa?' : text(c.title || c.field)}</h2>
    <div class="spot-readings">${readings.slice(0, 2).map((v) => `<div><strong>${text(v.value)}${days ? '<small> dni</small>' : ''}</strong>${v.source_period ? `<em>W dokumencie · ${text(v.source_period)}</em>` : ''}<span>${text(typeof v.source === 'object' ? v.source?.title : v.source, 'Dokument źródłowy')}</span></div>`).join('')}</div>
    <a class="spot-open" href="${projectURL(p.id)}/links">Porównaj źródła${variants.length > 2 ? ' (' + num(variants.length) + ')' : ''} ${icon('right')}</a>
  </section>`;
}
function home() {
  const s = store.stats,
    pending = store.reviews.filter((x) => x.status === 'pending'),
    list = store.projects;
  const disputed = list
    .flatMap((p) => arr(p.conflicts).map((c) => ({ p, c })))
    .sort((a, b) => Number(b.c.field === 'planned_days') - Number(a.c.field === 'planned_days'))[0];
  const recent = store.audit
    .flatMap((a) => a.detail?.projects || [a.subject])
    .filter((x) => typeof x === 'string');
  const sorted = [...new Set([...recent, ...list.map((p) => p.id)])].map(currProject).filter(Boolean);
  return (
    pagehead(
      'Pulpit inwestycji',
      'Baza doświadczeń sektora wodno-kanalizacyjnego.',
      linkBtn('#analiza', 'Nowa analiza', 'plus', 'primary')
    ) +
    `
 <div class="desk-lead${disputed ? ' has-evidence' : ''}">${disputed ? evidenceSpotlight(disputed) : ''}
 <section class="hero replay-feature" aria-labelledby="hero-title"><div><div class="hero-label">${icon('replay')} Symulacja historyczna</div><h2 id="hero-title">Próba generalna inwestycji</h2>
 <p>Oceń ryzyko przed przetargiem. Odsłoń dokumenty i porównaj swoją ocenę z przebiegiem prac.</p>${linkBtn('#proba', 'Rozpocznij próbę', 'right', 'mint')}</div></section></div>
 <div class="stats">${stat('Inwestycje w bazie', s.projects, '#baza/all', 'layers')}${stat('Dokumenty źródłowe', s.documents, '#dokumenty', 'file', 'tone-blue')}${stat('Do weryfikacji', s.pending, '#ekspert', 'verify', 'tone-orange')}${stat('Zakończone inwestycje', s.completed, '#baza/completed', 'checkfile', 'tone-purple')}</div>
 <div class="dashboard-grid"><section class="panel"><div class="section-head"><h2>Baza inwestycji</h2><a class="text-button" href="#baza/all">Zobacz wszystkie ${icon('right')}</a></div><div class="project-list">${sorted.slice(0, 5).map(projectRow).join('') || empty('Baza jest pusta. Zaimportuj pierwszy arkusz inwestycji.')}</div></section>
 <section class="panel"><div class="section-head"><h2>Do weryfikacji</h2><a class="text-button" href="#ekspert" aria-label="Otwórz panel eksperta">${icon('right')}</a></div><div class="feed">${
   pending
     .slice(0, 4)
     .map((x) => {
       const c = currProject(x.project_id);
       return `<button class="review-row feed-row" data-act="review" data-id="${esc(x.id)}"><span class="icon-tile">${icon('verify')}</span><span class="grow"><span class="title">${text(x.title || 'Powiązanie do oceny')}</span><span class="sub">${text(x.title === c?.title ? c.location || c.buyer : c?.title)}</span></span></button>`;
     })
     .join('') || empty('Wszystkie propozycje zostały rozpatrzone.')
 }</div></section></div>`
  );
}
let docsLimit = 45,
  docsQuery = '';
function documentRows() {
  const docs = store.projects
    .flatMap((p) => arr(p.documents).map((d) => ({ p, d })))
    .filter(({ p, d }) => matches({ ...p, title: p.title + ' ' + d.title + ' ' + (d.locator || '') }, docsQuery));
  return `<div class="section-head"><h2>Dokumenty</h2><span class="pill">${num(docs.length)}</span></div>${
    docs
      .slice(0, docsLimit)
      .map(
        ({ p, d }) =>
          `<div class="list-card"><div class="title">${text(d.title)}</div><a class="hint" href="${projectURL(p.id)}/docs">${text(p.title)} · ${text(d.locator, 'Dokument')}</a>${source(d, p)}</div>`
      )
      .join('') || empty('Brak dokumentów spełniających kryteria.')
  }${docs.length > docsLimit ? '<button class="button" data-act="more-docs">Pokaż kolejne</button>' : ''}`;
}
titles.dokumenty = 'Dokumenty źródłowe';
function allDocs() {
  return (
    pagehead('Dokumenty źródłowe', 'Przeszukaj dokumenty i otwórz inwestycję, do której należą.') +
    `<div class="panel">${field('Szukaj dokumentu lub inwestycji', `<input type="search" id="docs-search" value="${esc(docsQuery)}">`)}<div id="all-docs">${documentRows()}</div></div>`
  );
}
function loginView(error = '') {
  return `<div class="entry"><section class="entry-form"><div class="entry-brand"><img src="/static/assets/znak.svg" alt="">Risk Miner</div>
    <div><p><a href="/pokaz">Przejrzyj publiczne akta umowy</a></p><h1>Dostęp do Risk Minera</h1><form id="login-form">${error ? notice(error, true) : ''}${field('Token dostępu', '<input name="token" type="password" autofocus required autocomplete="current-password" aria-describedby="token-help"><small id="token-help">Wpisz token otrzymany od administratora.</small>')}
    <button class="button primary" type="submit">Zaloguj się ${icon('right')}</button>${statusLine}</form></div></section>
    <aside class="entry-photo"><div><span class="hero-label">${icon('water')} Inwestycje wodno-kanalizacyjne</span><p>Co warto sprawdzić<br>przed przetargiem?</p><span>Dokumenty, ryzyka i doświadczenia gmin w jednym miejscu.</span></div></aside></div>`;
}
let tokenRequired = false,
  loadError = '',
  routeGeneration = 0;
function paint() {
  const [view, id, tab] = active();
  document.body.classList.toggle('signin', tokenRequired && !store.loaded);
  chrome(view);
  if (!store.loaded) {
    main.innerHTML = tokenRequired
      ? loginView()
      : loadError
        ? pagehead('Baza jest niedostępna') +
          notice(loadError, true) +
          '<button class="button" data-act="reload">Spróbuj ponownie</button>'
        : '<p class="loading" role="status">Wczytywanie bazy doświadczeń…</p>';
    return;
  }
  const views = {
    pulpit: home,
    baza: () => caseList(id),
    projekt: () => caseDetail(id, tab),
    analiza: () => analysisView('analiza'),
    proba: () => analysisView('proba'),
    ekspert: () => reviewView(id),
    import: () => importView(id),
    katalog: catalogView,
    historia: auditView,
    dokumenty: allDocs,
  };
  main.innerHTML = Object.hasOwn(views, view)
    ? views[view]()
    : pagehead('Nie znaleziono widoku') + linkBtn('#pulpit', 'Wróć do pulpitu', 'grid');
}
async function route() {
  menu(false);
  closeDialog();
  const run = ++routeGeneration;
  paint();
  window.scrollTo(0, 0);
  main.focus({ preventScroll: true });
  const [view, id] = active();
  if (store.loaded && view === 'analiza' && id) {
    try {
      await restoreAnalysis(id);
      if (run === routeGeneration) paint();
    } catch (e) {
      if (run === routeGeneration) toast(e.message);
    }
  }
  if (store.loaded && view === 'projekt' && id) {
    try {
      const detail = await api(apiURL(id));
      if (run !== routeGeneration) return;
      const idx = store.projects.findIndex((x) => x.id === id);
      if (idx !== -1) store.projects[idx] = detail;
      else store.projects.push(detail);
      paint();
    } catch (e) {
      if (run === routeGeneration) toast(e.message);
    }
  }
}
async function init() {
  try {
    await sync();
    loadError = '';
    tokenRequired = false;
  } catch (e) {
    store.loaded = false;
    tokenRequired = e.status === 401;
    loadError = e.message;
  }
  await route();
}
function searchRows(q) {
  const found = store.projects.filter((p) => matches(p, q)),
    i = q ? 12 : 5;
  return found.slice(0, i).map(projectRow).join('') || empty('Nie znaleziono pasujących inwestycji.');
}
function searchModal() {
  if (!store.loaded) return;
  dialog(
    'Szukaj inwestycji',
    `${field('Nazwa, identyfikator lub miejscowość', '<input type="search" id="global-search" autofocus>')}<div id="global-results">${searchRows('')}</div>`
  );
}
async function action(b) {
  const a = b.dataset.act;
  if (a === 'close') {
    closeDialog();
    return;
  }
  if (a === 'menu') {
    menu(!document.body.classList.contains('menu-open'));
    return;
  }
  if (a === 'search') {
    searchModal();
    return;
  }
  if (a === 'reload') {
    await init();
    return;
  }
  if (a === 'account') {
    dialog(
      'Dostęp do aplikacji',
      `<p>${store.auth?.required ? 'Sesja powiązana z tokenem dostępu.' : 'Dostęp lokalny na tym komputerze.'}</p>${store.loaded ? `<p><b>${text(store.auth?.actor)}</b> · ${text(label(store.auth?.role))}</p>` : ''}${store.auth?.required ? '<button class="button" data-act="logout">Wyloguj się</button>' : ''}`
    );
    return;
  }
  if (a === 'logout') {
    sessionStorage.removeItem('riskminer-access');
    clearAnalysis();
    resetExperts();
    location.reload();
    return;
  }
  if (a === 'more-docs') {
    docsLimit += 45;
    document.querySelector('#all-docs').innerHTML = documentRows();
    return;
  }
  if (a === 'local-source') {
    const path = b.dataset.path;
    if (!/^\/api\/(?:files|knowledge)\/[\w.-]+$/.test(path)) throw new Error('Niepoprawny adres źródła.');
    const res = await request(path);
    if (path.startsWith('/api/files/')) {
      const cd = res.headers.get('content-disposition') || '';
      let name = b.dataset.name || 'dokument';
      const m = cd.match(/filename\*=UTF-8''([^;]+)/i);
      try {
        if (m) name = decodeURIComponent(m[1]);
      } catch {}
      await saveBlob(await res.blob(), name);
    } else {
      const r = await res.json();
      dialog(
        r.title || r.source || 'Materiał ekspercki',
        `<p class="hint">${text(r.locator, '')}</p><blockquote>${text(r.excerpt || r.text)}</blockquote>${r.original_url ? `<button class="button" data-act="local-source" data-path="${esc(r.original_url)}" data-name="${esc(r.source)}">Pobierz oryginalny dokument Word</button>` : ''}`
      );
    }
    return;
  }
  if (handleExpertAction(a, b) || (await handleCaseAction(a, b, paint)) || (await handleAnalysisAction(a, b)))
    return;
}
document.addEventListener('click', (e) => {
  if (e.target.closest('.skip')) {
    e.preventDefault();
    main.focus();
    return;
  }
  const b = e.target.closest('[data-act]');
  if (b) {
    e.preventDefault();
    action(b).catch((err) => toast(err.message));
    return;
  }
  const anchor = e.target.closest('a[href^="#"]');
  if (anchor) {
    if (document.querySelector('#modal').open) closeDialog();
    menu(false);
    if (anchor.hash === location.hash && anchor.hash !== '#main') route();
  }
});
document.addEventListener('submit', (e) => {
  if (handleAnalysisSubmit(e) || handleExpertSubmit(e, paint) || handleCaseSubmit(e, paint)) return;
  if (e.target.id === 'login-form') {
    e.preventDefault();
    const f = e.target;
    submitTask(f, async () => {
      const token = new FormData(f).get('token');
      sessionStorage.setItem('riskminer-access', String(token).trim());
      try {
        await sync();
      } catch (e) {
        sessionStorage.removeItem('riskminer-access');
        throw e;
      }
      tokenRequired = false;
      await route();
    });
  }
});
document.addEventListener('change', (e) => {
  handleAnalysisChange(e);
  handleExpertChange(e);
  if (e.target.type !== 'search') handleCaseInput(e);
});
document.addEventListener('input', (e) => {
  handleDraftInput(e);
  if (e.target.id === 'global-search')
    document.querySelector('#global-results').innerHTML = searchRows(e.target.value);
  if (e.target.id === 'docs-search') {
    docsQuery = e.target.value;
    docsLimit = 45;
    document.querySelector('#all-docs').innerHTML = documentRows();
  }
  if (e.target.type === 'search') handleCaseInput(e);
});
document.addEventListener('keydown', (e) => {
  if (
    e.key === '/' &&
    !e.altKey &&
    !e.metaKey &&
    !e.ctrlKey &&
    !e.target.matches('input,textarea,select,[contenteditable=true]') &&
    !document.querySelector('#modal').open
  ) {
    e.preventDefault();
    searchModal();
  }
  if (e.key === 'Escape') menu(false);
});
document.querySelector('#modal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeDialog();
});
window.addEventListener('hashchange', route);
window.matchMedia('(max-width:720px)').addEventListener('change', () => menu(false));
document.querySelector('#search-icon').innerHTML = icon('search');
init();
