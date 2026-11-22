import {
  api,
  apiURL,
  arr,
  closeDialog,
  currProject,
  date,
  dialog,
  empty,
  esc,
  field,
  icon,
  label,
  linkBtn,
  money,
  notice,
  num,
  pagehead,
  pill,
  projectRow,
  projectURL,
  recordDetails,
  request,
  saveBlob,
  selectOptions,
  source,
  statusLine,
  store,
  submitTask,
  sync,
  text,
  toast,
  writable,
} from './lib.js';
import { useAsDraft } from './analysis.js';
import { kindLabel } from './expert.js';

let filters = { query: '', status: '', dataset: '', limit: 40 };
const fold = (s) =>
  String(s || '')
    .toLocaleLowerCase('pl-PL')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/ł/g, 'l');
export function matches(p, q) {
  return fold([p.title, p.location, p.buyer, p.cst, p.id].join(' ')).includes(fold(q).trim());
}
function matchingList() {
  const list = store.projects.filter(
    (p) =>
      (!filters.status || p.status === filters.status) &&
      (!filters.dataset || p.dataset === filters.dataset) &&
      matches(p, filters.query)
  );
  return `<div class="section-head"><h2>Inwestycje</h2><span class="pill">${list.length}</span></div>${list.slice(0, filters.limit).map(projectRow).join('') || empty('Brak inwestycji spełniających wybrane kryteria.')}${list.length > filters.limit ? '<button class="button" data-act="more-projects">Pokaż kolejne</button>' : ''}`;
}
export function caseList(active) {
  if (active === 'completed') filters.status = 'completed';
  else if (active === 'all') filters = { query: '', status: '', dataset: '', limit: 40 };
  return (
    pagehead(
      'Baza inwestycji',
      'Przeglądaj przypadki, źródła i historię realizacji projektów.',
      `<button class="button" data-act="export">${icon('download')} Eksport</button>` +
        (writable() ? linkBtn('#import', 'Importuj dane', 'upload', 'primary') : '')
    ) +
    `<div class="panel"><form class="toolbar" id="project-filter">
 <label class="field wide">Szukaj inwestycji<input name="query" value="${esc(filters.query)}" type="search" placeholder="Nazwa, miejscowość lub identyfikator"></label>
 ${field(
   'Status',
   `<select name="status">${selectOptions(
     [
       ['', 'Wszystkie statusy'],
       ['planned', 'Planowana'],
       ['active', 'W realizacji'],
       ['completed', 'Zakończona'],
     ],
     filters.status
   )}</select>`
 )}
 ${field('Zbiór', `<select name="dataset">${selectOptions([['', 'Wszystkie zbiory'], ...[...new Set(store.projects.map((p) => p.dataset).filter(Boolean))].map((x) => [x, label(x)])], filters.dataset)}</select>`)}</form><div id="project-rows">${matchingList()}</div></div>`
  );
}
const sections = {
  overview: 'Karta inwestycji',
  links: 'Kontrakty i zmiany',
  docs: 'Dokumenty',
  events: 'Zdarzenia i pomiary',
};
function dataGrid(a) {
  return `<dl class="detail-grid">${a.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${text(v)}</dd></div>`).join('')}</dl>`;
}
const named = (p, group, id) => arr(p[group]).find((x) => x.id === id)?.title || id;
const editRecord = (p, item, group) =>
  writable()
    ? `<button class="text-button" data-act="record-edit" data-id="${esc(p.id)}" data-group="${esc(group)}" data-entity="${esc(item.id)}">${icon('edit')} Edytuj metadane</button>`
    : '';
function facts(item) {
  return [
    item.fact_type === 'proposed' ? 'Wartość wnioskowana' : null,
    item.kind === 'signal' ? 'Sygnał do oceny' : null,
    item.exemplary ? 'Materiał wzorcowy' : null,
  ]
    .filter(Boolean)
    .map((s) => `<span class="pill">${s}</span>`)
    .join(' ');
}
function recordCard(item, p, group) {
  const doc = arr(p.documents).find((d) => d.id === item.source_id);
  const r = store.reviews.find((r) => r.entity_id === item.id);
  return `<article class="list-card"><div class="card-head"><div><span class="eyebrow">${esc(kindLabel(group))}</span><h3>${text(item.title || item.external_id || item.id)}</h3></div>${pill(item.status)}</div>
 ${item.description ? `<p>${esc(item.description)}</p>` : ''}
 ${item.value != null ? `<p><strong>${esc(item.value)} ${text(item.unit, '')}</strong></p>` : ''}
 ${item.contract_id ? `<p class="hint">Kontrakt · ${text(named(p, 'contracts', item.contract_id))}</p>` : ''}
 ${item.procedure_id ? `<p class="hint">Postępowanie · ${text(named(p, 'procedures', item.procedure_id))}</p>` : ''}
 ${doc ? source({ ...doc, excerpt: item.excerpt || doc.excerpt }, p) : ''}
 ${facts(item)}<div class="actions">${r ? `<button class="text-button" data-act="review" data-id="${esc(r.id)}">${icon('verify')} Decyzja ekspercka</button>` : ''}${editRecord(p, item, group)}</div>${recordDetails(item)}</article>`;
}
function byGroup(p, group, title) {
  return `<section class="panel"><div class="section-head"><h2>${esc(title)}</h2><span class="pill">${arr(p[group]).length}</span></div><div class="card-list">${
    arr(p[group])
      .map((i) => recordCard(i, p, group))
      .join('') || empty('Brak zapisanych rekordów w tej grupie.')
  }</div></section>`;
}
function conflicts(p) {
  const items = [...arr(p.conflicts), ...arr(p.projection_conflicts)];
  if (!items.length) return '';
  const fieldNames = {
    planned_days: 'Okres realizacji umowy',
    paid_pln: 'Wypłacone wynagrodzenie',
    finished_on: 'Data wykonania',
    signed_on: 'Data zawarcia umowy',
    agreed_period: 'Uzgodniony okres realizacji',
  };
  return `<section class="panel"><h2>Rozbieżności między źródłami</h2>${items
    .map(
      (c) =>
        `<article class="list-card evidence-comparison"><h3>${text(c.title || fieldNames[c.field] || c.field)}</h3><p class="hint contract-key">Umowa · ${text(c.contract_key)}</p><div class="variant-grid">${arr(
          c.variants
        )
          .map(
            (v) =>
              `<section class="variant"><div class="variant-head"><strong>${text(v.value)}${c.field === 'planned_days' ? ' dni' : ''}</strong>${v.status ? pill(v.status) : ''}</div>${v.source_period ? `<small>W dokumencie · ${text(v.source_period)}</small>` : ''}${source(v.field_reference || (typeof v.source === 'object' ? v.source : { id: v.source_id, title: v.source, url: v.url }), p)}</section>`
          )
          .join('')}</div></article>`
    )
    .join('')}</section>`;
}
function impacts(p) {
  const groups = arr(p.contract_impacts).filter((c) =>
    ['events', 'measures', 'changes'].some((k) => arr(c[k]).length)
  );
  if (!groups.length) return '';
  return `<section class="panel"><h2>Ustalenia przypisane do kontraktów</h2>${groups
    .map(
      (c) =>
        `<article class="list-card"><h3>${text(c.title || c.contract_id)}</h3>${['events', 'measures', 'changes']
          .map((k) =>
            arr(c[k])
              .map(
                (i) =>
                  `<div><strong>${text(i.title)}</strong> ${i.value != null ? esc(i.value) + ' ' + text(i.unit, '') : ''} ${facts(i)}${i.source_id ? source(i.source_id, p) : ''}</div>`
              )
              .join('')
          )
          .join('')}</article>`
    )
    .join('')}</section>`;
}
function overview(p) {
  const entries = [
    ...arr(p.documents)
      .filter((x) => x.published_at)
      .map((x) => ({ at: x.published_at, title: x.title, kind: 'Publikacja źródła', ref: x })),
    ...arr(p.changes)
      .filter((x) => x.published_at)
      .map((x) => ({
        at: x.published_at,
        title: x.title,
        kind: 'Zmiana kontraktu',
        ref: arr(p.documents).find((d) => d.id === x.source_id),
      })),
  ].sort((a, b) => String(a.at).localeCompare(String(b.at)));
  return `<div class="columns"><section class="panel"><h2>Zakres i parametry</h2>${p.description ? `<p class="preserve">${esc(p.description)}</p>` : empty('Brak opisu zakresu w danych źródłowych.')}
 ${dataGrid([
   ['Zamawiający', p.buyer],
   ['Lokalizacja', p.location],
   ['Typ', p.type],
   ['Sektor', p.sector],
   ['Koszt planowany', money(p.planned_cost)],
   ['Koszt końcowy', money(p.actual_cost)],
   ['Czas planowany', p.planned_days != null ? num(p.planned_days) + ' dni' : '—'],
   ['Czas rzeczywisty', p.actual_days != null ? num(p.actual_days) + ' dni' : '—'],
   ['Identyfikator projektu', p.cst || p.id],
   ['Obiekt czynny podczas prac', p.live_operation == null ? 'Brak danych' : p.live_operation ? 'Tak' : 'Nie'],
 ])}
 ${[p.plan_source_id, p.outcome_source_id]
   .filter(Boolean)
   .map((id) => source(id, p))
   .join('')}
 </section><section class="panel"><div class="section-head"><h2>Oś czasu źródeł</h2>${icon('clock')}</div>${
   entries.length
     ? `<ol class="timeline">${entries
         .slice(0, 16)
         .map(
           (x) =>
             `<li><small>${date(x.at)} · ${esc(x.kind)}</small><div class="title">${text(x.title)}</div>${x.ref ? source(x.ref, p) : ''}</li>`
         )
         .join(
           ''
         )}</ol>${entries.length > 16 ? linkBtn(projectURL(p.id) + '/docs', 'Pełna dokumentacja', 'file') : ''}`
     : empty('Oś czasu pojawi się po dodaniu dokumentów z datą publikacji.')
 }</section></div>`;
}
export function caseDetail(pid, tab = 'overview') {
  const p = currProject(pid);
  if (!p) return pagehead('Nie znaleziono inwestycji') + linkBtn('#baza', 'Wróć do bazy', 'layers');
  const selected = Object.hasOwn(sections, tab) ? tab : 'overview',
    base = projectURL(pid);
  const toolbar = `<button class="button" data-act="export" data-id="${esc(pid)}">${icon('download')} Eksport</button>${writable() ? `<button class="button" data-act="edit-project" data-id="${esc(pid)}">${icon('edit')} Edytuj</button>` : ''}<button class="button primary" data-act="as-draft" data-id="${esc(pid)}">${icon('analysis')} Analizuj plan</button>`;
  let inner = overview(p);
  if (selected === 'docs')
    inner = `<section class="panel"><div class="section-head"><h2>Dokumenty źródłowe</h2>${writable() ? linkBtn('#import/' + encodeURIComponent(pid), 'Dodaj dokument', 'plus') : ''}</div>${
      arr(p.documents)
        .map(
          (d) =>
            `<article class="list-card"><div class="card-head"><strong>${text(d.title)}</strong>${pill(d.status)}</div>${source(d, p)}${facts(d)}${editRecord(p, d, 'documents')}</article>`
        )
        .join('') || empty('Brak dokumentów źródłowych.')
    }</section>`;
  if (selected === 'links')
    inner = `<div class="stack">${arr(p.projection_warnings)
      .map((w) => notice(w, true))
      .join('')}${
      arr(p.contract_benchmarks).length
        ? `<section class="panel"><h2>Udokumentowane wyniki umów na roboty</h2>${p.contract_benchmarks
            .map(
              (c) =>
                `<details><summary>${text(c.contract_key)} · ${c.lot ? 'część ' + esc(c.lot) : 'cały zakres umowy'}</summary>${dataGrid(
                  [
                    ['Kwota umowy', money(c.planned_cost)],
                    ['Kwota wypłacona', money(c.actual_cost)],
                    ['Plan umowy (dni)', num(c.planned_days)],
                    ['Realizacja umowy (dni)', num(c.actual_days)],
                  ]
                )}${arr(c.warnings)
                  .map((w) => notice(w, true))
                  .join('')}${arr(c.source_ids)
                  .map((id) => source(id, p))
                  .join('')}</details>`
            )
            .join('')}</section>`
        : ''
    }<div class="columns"><div class="stack">${byGroup(p, 'procedures', 'Postępowania')}${byGroup(p, 'contracts', 'Kontrakty')}</div><div class="stack">${byGroup(p, 'changes', 'Zmiany kontraktów')}${byGroup(p, 'observations', 'Ogłoszenia i powiązania')}</div></div></div>`;
  if (selected === 'links') inner = `<div class="stack">${conflicts(p)}${impacts(p)}${inner}</div>`;
  if (selected === 'events')
    inner = `<div class="columns">${byGroup(p, 'events', 'Zdarzenia i sygnały')}${byGroup(p, 'measurements', 'Pomiary')}</div>`;
  return (
    pagehead(p.title, p.buyer || p.location || '', toolbar) +
    `<div class="meta">${pill(p.status)}${pill(p.dataset)}${p.exemplary ? '<span class="pill positive">Przypadek wzorcowy</span>' : ''}</div>
 <nav class="tabbar" aria-label="Sekcje inwestycji">${Object.entries(sections)
   .map(
     ([id, t]) =>
       `<a class="tab ${id === selected ? 'active' : ''}" href="${base}/${id}" ${id === selected ? 'aria-current="page"' : ''}>${t}</a>`
   )
   .join('')}</nav>
 ${writable() ? `<div class="actions case-actions"><button class="button" data-act="enrich" data-id="${esc(pid)}">${icon('refresh')} Wyszukaj w źródłach</button>${linkBtn('#ekspert/' + encodeURIComponent(pid), 'Oceń powiązania', 'verify')}</div>` : ''}${inner}`
  );
}
function editModal(id) {
  const p = currProject(id),
    input = (k, t = 'text') =>
      `<input name="${k}" type="${t}" value="${esc(p[k] ?? '')}" ${t === 'number' ? 'min="0" step="any"' : ''} ${k === 'title' ? 'required' : ''}>`,
    docOpts = [
      ['', 'Brak wskazania'],
      ...arr(p.documents).map((d) => [d.id, [d.title, d.locator].filter(Boolean).join(' · ')]),
    ];
  dialog(
    'Edycja inwestycji',
    `<form id="case-edit" data-id="${esc(id)}">${field('Tytuł', input('title'))}${field('Opis', `<textarea name="description" rows="3">${esc(p.description)}</textarea>`)}
 <div class="fields">${[
   ['Zamawiający', 'buyer'],
   ['Miejscowość', 'location'],
   ['Sektor', 'sector'],
   ['Typ inwestycji', 'type'],
 ]
   .map(([t, k]) => field(t, input(k)))
   .join('')}</div>
 ${field(
   'Status',
   `<select name="status">${selectOptions(
     [
       ['planned', 'Planowana'],
       ['active', 'W realizacji'],
       ['completed', 'Zakończona'],
     ],
     p.status
   )}</select>`
 )}
 <div class="fields">${[
   ['Czas planowany (dni)', 'planned_days'],
   ['Czas rzeczywisty (dni)', 'actual_days'],
   ['Planowany koszt (zł)', 'planned_cost'],
   ['Końcowy koszt (zł)', 'actual_cost'],
 ]
   .map(([t, k]) => field(t, input(k, 'number')))
   .join('')}</div>
 ${field('Dokument potwierdzający plan', `<select name="plan_source_id">${selectOptions(docOpts, p.plan_source_id)}</select>`)}${field('Dokument potwierdzający wykonanie', `<select name="outcome_source_id">${selectOptions(docOpts, p.outcome_source_id)}</select>`)}
 <div class="fields">${[
   ['Data planu', 'planned_at'],
   ['Początek', 'start_date'],
   ['Koniec', 'end_date'],
   ['Zakończono', 'completed_at'],
 ]
   .map(([t, k]) => field(t, input(k, 'date')))
   .join('')}</div>
 ${field(
   'Tryb pracy obiektu',
   `<select name="live_operation">${selectOptions(
     [
       ['', 'Brak informacji'],
       ['true', 'Czynny podczas prac'],
       ['false', 'Wyłączony podczas prac'],
     ],
     p.live_operation ?? ''
   )}</select>`
 )}
 <label class="check"><input type="checkbox" name="exemplary" ${p.exemplary ? 'checked' : ''}> Oznacz jako przypadek wzorcowy</label><button class="button primary" type="submit">Zapisz zmiany</button>${statusLine}</form>`
  );
}
export function handleCaseInput(e) {
  const f = e.target.form;
  if (f?.id === 'project-filter') {
    Object.assign(filters, Object.fromEntries(new FormData(f)), { limit: 40 });
    document.querySelector('#project-rows').innerHTML = matchingList();
  }
}
export async function handleCaseAction(act, b, repaint) {
  const id = b.dataset.id;
  if (act === 'record-edit') {
    const p = currProject(id),
      g = b.dataset.group,
      i = arr(p[g]).find((x) => x.id === b.dataset.entity);
    if (!i) throw new Error('Nie znaleziono rekordu.');
    const refs = (key, group, t) =>
      field(
        t,
        `<select name="${key}">${selectOptions(
          [
            ['', 'Bez przypisania'],
            ...arr(p[group])
              .filter((x) => x.id !== i.id)
              .map((x) => [x.id, x.title || x.id]),
          ],
          i[key]
        )}</select>`
      );
    dialog(
      'Korekta metadanych',
      `<form id="record-edit-form" data-id="${esc(id)}" data-group="${esc(g)}" data-entity="${esc(i.id)}"><p class="hint">${text(p.title)} · ${esc(kindLabel(g))}</p>
   ${field('Tytuł', `<input name="title" value="${esc(i.title)}" required>`)}
   ${field('Opis eksperta', `<textarea name="description" rows="3">${esc(i.description)}</textarea>`)}
   ${field('Rodzaj dokumentu lub rekordu', `<input name="kind" value="${esc(i.kind)}">`)}
   ${field('Data publikacji', `<input name="published_at" type="date" value="${esc(String(i.published_at || '').slice(0, 10))}">`)}
   ${g !== 'contracts' && arr(p.contracts).length ? refs('contract_id', 'contracts', 'Kontrakt') : ''}${g !== 'procedures' && arr(p.procedures).length ? refs('procedure_id', 'procedures', 'Postępowanie') : ''}
   <label class="check"><input type="checkbox" name="exemplary" ${i.exemplary ? 'checked' : ''}> Oznacz jako materiał wzorcowy</label>
   ${field('Uzasadnienie korekty', `<textarea name="comment" rows="2" required maxlength="3000"></textarea>`)}
   <button class="button primary" type="submit">Zapisz korektę</button>${statusLine}</form>`
    );
    return true;
  }
  if (act === 'as-draft') {
    useAsDraft(currProject(id));
    return true;
  }
  if (act === 'edit-project') {
    editModal(id);
    return true;
  }
  if (act === 'more-projects') {
    filters.limit += 40;
    document.querySelector('#project-rows').innerHTML = matchingList();
    return true;
  }
  if (act === 'export') {
    dialog(
      'Eksport danych',
      `<p>${id ? 'Inwestycja: ' + text(currProject(id)?.title) : 'Wszystkie inwestycje, powiązania i decyzje eksperckie.'}</p><div class="actions">${['json', 'csv'].map((fmt) => `<button class="button" data-act="export-file" data-id="${esc(id)}" data-format="${fmt}">${icon('download')} Pobierz ${fmt.toUpperCase()}</button>`).join('')}</div>`
    );
    return true;
  }
  if (act === 'export-file') {
    const fmt = b.dataset.format;
    const qs = new URLSearchParams({ format: fmt });
    if (id) qs.set('project_id', id);
    const r = await request('/api/export?' + qs);
    await saveBlob(await r.blob(), `risk-miner.${fmt}`);
    closeDialog();
    return true;
  }
  if (act === 'enrich') {
    b.disabled = true;
    b.textContent = 'Trwa wyszukiwanie…';
    try {
      const r = await api(apiURL(id) + '/enrich', { method: 'POST', body: {} });
      await sync();
      repaint();
      dialog(
        'Wynik wyszukiwania',
        `<p>Znalezione rekordy: <b>${num(r.found)}</b>. Nowe rekordy w kolejce: <b>${num(r.added)}</b>.</p>${arr(
          r.warnings
        )
          .map((w) => notice(w, true))
          .join('')}${linkBtn('#ekspert/' + encodeURIComponent(id), 'Przejdź do weryfikacji', 'verify')}`
      );
    } finally {
      if (b.isConnected) {
        b.disabled = false;
        b.innerHTML = icon('refresh') + ' Wyszukaj w źródłach';
      }
    }
    return true;
  }
  return false;
}
export function handleCaseSubmit(e, repaint) {
  const f = e.target;
  if (f.id === 'project-filter') {
    e.preventDefault();
    return true;
  }
  if (f.id === 'record-edit-form') {
    e.preventDefault();
    submitTask(f, async () => {
      const d = new FormData(f),
        p = currProject(f.dataset.id),
        i = arr(p[f.dataset.group]).find((x) => x.id === f.dataset.entity),
        fields = {};
      for (const [k, v] of d) {
        if (k === 'comment' || k === 'exemplary') continue;
        const original = k === 'published_at' ? String(i[k] || '').slice(0, 10) : String(i[k] || '');
        if (original !== v) fields[k] = v || null;
      }
      if (Boolean(i.exemplary) !== d.has('exemplary')) fields.exemplary = d.has('exemplary');
      if (!Object.keys(fields).length) throw new Error('Wprowadź zmianę w metadanych.');
      await api(apiURL(p.id) + '/records/' + encodeURIComponent(i.id), {
        method: 'PATCH',
        body: { fields, comment: d.get('comment') },
      });
      await sync();
      const idx = store.projects.findIndex((x) => x.id === p.id);
      if (idx >= 0) store.projects[idx] = await api(apiURL(p.id));
      closeDialog();
      repaint();
      toast('Zapisano korektę i jej uzasadnienie.');
    });
    return true;
  }
  if (f.id !== 'case-edit') return false;
  e.preventDefault();
  submitTask(f, async () => {
    const d = new FormData(f),
      p = currProject(f.dataset.id),
      fields = {};
    for (const [k, v] of d) {
      let val = v || null;
      if (['planned_days', 'actual_days', 'planned_cost', 'actual_cost'].includes(k))
        val = v === '' ? null : Number(v);
      if (k === 'live_operation') val = v === '' ? null : v === 'true';
      if (k !== 'exemplary' && (p[k] ?? null) !== val) fields[k] = val;
    }
    if (Boolean(p.exemplary) !== d.has('exemplary')) fields.exemplary = d.has('exemplary');
    await api(apiURL(p.id), { method: 'PATCH', body: { fields } });
    await sync();
    closeDialog();
    repaint();
    toast('Zapisano dane inwestycji.');
  });
  return true;
}
