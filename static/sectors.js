import {
  api,
  arr,
  closeDialog,
  dialog,
  empty,
  esc,
  field,
  icon,
  selectOptions,
  source,
  statusLine,
  store,
  submitTask,
  sync,
  text,
  toast,
} from './lib.js';

export const sectors = () => arr(store.sectors);
export function sectorFor(project = {}) {
  const data = sectors();
  const name = String(project.sector || '')
    .trim()
    .toLocaleLowerCase('pl');
  const current =
    data.find((s) => s.id === project.sector_id) ||
    data.find((s) =>
      [s.id, s.name, ...arr(s.aliases)].some((v) => String(v).trim().toLocaleLowerCase('pl') === name)
    );
  return current || data.find((s) => s.id === 'water') || data[0];
}
export function sectorOptions(project) {
  return selectOptions(
    sectors().map((s) => [s.id, s.name]),
    sectorFor(project)?.id
  );
}
export function sectorTypes(project) {
  const s = sectorFor(project);
  return s
    ? arr(s.types).map((t) => t.name)
    : [...new Set(store.projects.map((p) => p.type).filter(Boolean))].sort();
}
export function sectorPanel() {
  const admin = store.auth.role === 'admin';
  return `<section class="panel"><div class="section-head"><h2>Sektory</h2>${admin ? `<button class="button" data-act="sector-new">${icon('plus')} Dodaj sektor</button>` : ''}</div>
    <div class="card-list">${
      sectors()
        .map(
          (
            s
          ) => `<article class="list-card"><div class="card-head"><h3>${text(s.name)}</h3>${admin ? `<button class="text-button" data-act="sector-edit" data-id="${esc(s.id)}">${icon('edit')} Edytuj sektor</button>` : ''}</div><p>${text(s.description, '')}</p>
      <details><summary>Typy inwestycji i aliasy</summary><p class="hint">Aliasy · ${arr(s.aliases).map(esc).join(', ') || 'brak'}</p>${
        arr(s.types)
          .map(
            (t) =>
              `<p><b>${text(t.name)}</b> · ${arr(t.terms).map(esc).join(', ')}</p>${t.source ? source(t.source) : ''}`
          )
          .join('') || empty('Brak zdefiniowanych typów.')
      }</details></article>`
        )
        .join('') || empty('Katalog sektorów jest pusty.')
    }</div></section>`;
}
export function sectorRuleFields(rule) {
  if (!sectors().length) return '';
  const selected = arr(rule.sector_ids).length ? rule.sector_ids : ['water'];
  return `<fieldset class="sector-choices"><legend>Sektory stosowania reguły</legend>${sectors()
    .map(
      (s) =>
        `<label class="check"><input type="checkbox" name="sector_ids" value="${esc(s.id)}" ${selected.includes(s.id) ? 'checked' : ''}> ${text(s.name)}</label>`
    )
    .join('')}</fieldset>`;
}
function sectorModal(id) {
  const s = sectors().find((item) => item.id === id) || {};
  dialog(
    id ? 'Edycja sektora' : 'Nowy sektor',
    `<form id="sector-form" data-id="${esc(id)}">
    ${field('Identyfikator sektora', `<input name="id" required ${id ? 'readonly' : ''} maxlength="64" pattern="[a-z0-9][a-z0-9_\\-]{0,63}" value="${esc(s.id)}" placeholder="np. transport"><small>Użyj małych liter bez znaków diakrytycznych, cyfr, myślnika lub podkreślenia.</small>`)}
    ${field('Nazwa sektora', `<input name="name" required maxlength="160" value="${esc(s.name)}">`)}
    ${field('Opis', `<textarea name="description" rows="2" maxlength="5000">${esc(s.description)}</textarea>`)}
    ${field('Aliasy (jeden w wierszu)', `<textarea name="aliases" rows="2">${esc(arr(s.aliases).join('\n'))}</textarea>`)}
    ${field(
      'Typy inwestycji i frazy rozpoznawcze',
      `<textarea name="types" rows="5" required placeholder="Modernizacja linii | torowisko; stacja kolejowa">${esc(
        arr(s.types)
          .map((t) => t.name + ' | ' + arr(t.terms).join('; '))
          .join('\n')
      )}</textarea><small>Jeden typ w wierszu. Oddziel nazwę typu od fraz znakiem |, a kolejne frazy średnikiem.</small>`
    )}
    <button class="button primary" type="submit">${icon('check')} Zapisz sektor</button>${statusLine}</form>`
  );
}
export function sectorAction(action, b) {
  if (action !== 'sector-edit' && action !== 'sector-new') return false;
  sectorModal(b.dataset.id || '');
  return true;
}
const lines = (value) =>
  String(value || '')
    .split('\n')
    .map((x) => x.trim())
    .filter(Boolean);
export function sectorSubmit(e, repaint) {
  const f = e.target;
  if (f.getAttribute('id') !== 'sector-form') return false;
  e.preventDefault();
  submitTask(f, async () => {
    const d = new FormData(f),
      id = String(d.get('id')).trim(),
      name = String(d.get('name')).trim(),
      existing = sectors().find((s) => s.id === id);
    if (!id || !name) throw new Error('Podaj identyfikator i nazwę sektora.');
    if (existing && !f.dataset.id) throw new Error('Ten identyfikator sektora już istnieje.');
    const types = lines(d.get('types')).map((line, i) => {
      const parts = line.split('|');
      if (parts.length !== 2 || !parts[0].trim())
        throw new Error('Wiersz ' + (i + 1) + ' wymaga nazwy typu i separatora |.');
      const terms = parts[1]
        .split(';')
        .map((t) => t.trim())
        .filter(Boolean);
      const name = parts[0].trim();
      return { ...arr(existing?.types).find((t) => t.name === name), name, terms };
    });
    const next = {
      ...existing,
      id,
      name,
      description: String(d.get('description')).trim(),
      aliases: lines(d.get('aliases')),
      types,
    };
    const entries = existing ? sectors().map((s) => (s.id === id ? next : s)) : [...sectors(), next];
    await api('/api/sectors', { method: 'PUT', body: { sectors: entries } });
    await sync();
    closeDialog();
    repaint();
    toast('Zapisano definicję sektora.');
  });
  return true;
}
