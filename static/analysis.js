import {
  api,
  arr,
  closeDialog,
  currProject,
  date,
  dialog,
  empty,
  esc,
  evidence,
  field,
  icon,
  label,
  linkBtn,
  money,
  notice,
  num,
  pagehead,
  pill,
  projectURL,
  request,
  saveBlob,
  selectOptions,
  source,
  statusLine,
  store,
  submitTask,
  text,
  toast,
  writable,
} from './lib.js';
import { sectorFor, sectorOptions, sectors, sectorTypes } from './sectors.js';
import { changeSensitivity, sensitivityPanel } from './sensitivity.js';

const modes = {
  analiza: { draft: {}, filters: {}, result: null },
  proba: { id: '', cutoff: '', filters: {}, result: null },
};
export function clearAnalysis() {
  for (const m of Object.values(modes)) {
    m.result = null;
    m.filters = {};
    m.draft = {};
    m.id = '';
    m.cutoff = '';
  }
}
const metricLabel = {
  cost_change_pct: 'Zmiana kosztu',
  days_change: 'Zmiana terminu',
  actual_days: 'Czas realizacji',
};
const metricUnit = { cost_change_pct: '%', days_change: ' dni', actual_days: ' dni' };
const scopes = [
  ['project', 'Całe przedsięwzięcie'],
  ['contract', 'Jedna umowa na roboty'],
];
const metricValue = (v, key) => (v == null ? '—' : num(v) + metricUnit[key]);
const formInput = (n, t = 'text', val = '', extra = '') =>
  `<input name="${n}" type="${t}" value="${esc(val ?? '')}" ${extra}>`;
const previewToggle = (f) =>
  `<label class="check"><input type="checkbox" name="preview_links" ${f.preview_links ? 'checked' : ''}> Podgląd powiązań po identyfikatorach</label>`;
function planningDate(p) {
  return (
    arr(p?.documents)
      .filter((d) => ['notice', 'plan', 'tender_notice', 'specification'].includes(d.kind) && d.published_at)
      .map((d) => d.published_at)
      .sort()[0] ||
    p?.planned_at ||
    p?.start_date ||
    ''
  );
}

function analysisForm() {
  const p = modes.analiza.draft;
  return `<form class="panel" id="analysis-form"><div class="section-head"><h2>Plan inwestycji</h2>${icon('note')}</div>
 ${!Object.keys(p).length ? '<button type="button" class="text-button" data-act="example-plan">Sprawdź przykład umowy na 365 dni</button>' : ''}
 ${field('Nazwa inwestycji', formInput('title', 'text', p.title, 'maxlength="500" placeholder="Np. Rozbudowa oczyszczalni"'))}
 ${field('Opis zakresu', `<textarea name="description" rows="4" maxlength="100000" placeholder="Opisz zakres prac lub dołącz dokumentację poniżej.">${esc(p.description)}</textarea>`)}
 ${sectors().length ? field('Sektor', `<select name="sector_id">${sectorOptions(p)}</select><small id="selected-sector-description">${text(sectorFor(p)?.description, '')}</small>`) : ''}
 ${field(
   'Typ inwestycji',
   `<input name="type" list="project-types" value="${esc(p.type)}" placeholder="Wpisz lub wybierz"><datalist id="project-types">${sectorTypes(
     p
   )
     .map((v) => `<option value="${esc(v)}"></option>`)
     .join('')}</datalist>`
 )}
 <div class="fields">${field('Planowany czas (dni)', formInput('planned_days', 'number', p.planned_days, 'min="1" step="1"'))}${field('Budżet (zł)', formInput('planned_cost', 'number', p.planned_cost, 'min="0" step="0.01"'))}</div>
 ${field('Zakres podanych kwot i terminów', `<select name="metric_scope">${selectOptions(scopes, p.metric_scope || 'project')}</select>`)}
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
 <div class="divider"></div>${field('Dokumenty do analizy', `<input type="file" name="attachment" accept=".pdf,.docx,.xlsx,.xls,.csv,.txt" multiple><small>Możesz dołączyć opis projektu lub uzupełniający załącznik.</small>`)}
 ${arr(p.documents).length ? `<div class="card-list">${p.documents.map((d, i) => `<div class="row"><span class="grow hint">${esc(d.title || d.source || 'Dokument')}</span><button type="button" class="ghost square" aria-label="Usuń dokument" data-act="remove-doc" data-index="${i}">${icon('close')}</button></div>`).join('')}</div>` : ''}
 ${previewToggle(modes.analiza.filters)}<button type="submit" class="button primary">${icon('analysis')} Analizuj inwestycję</button>${statusLine}</form>`;
}
function replayForm() {
  const m = modes.proba,
    candidates = store.projects.filter(
      (p) =>
        p.status === 'completed' ||
        arr(p.documents).some((d) => d.published_at && ['notice', 'completion', 'award'].includes(d.kind))
    );
  if (!candidates.length)
    return `<div class="panel">${notice('Do przeprowadzenia próby potrzebna jest zakończona inwestycja z datowanymi dokumentami.')}${linkBtn('#import', 'Importuj projekt', 'upload')}</div>`;
  const wellDated = candidates.filter(
    (p) =>
      planningDate(p) && arr(p.documents).some((d) => d.kind === 'completion' && d.published_at > planningDate(p))
  );
  const chosen =
      currProject(m.id) ||
      wellDated.sort((a, b) => planningDate(b).localeCompare(planningDate(a)))[0] ||
      candidates[0],
    cutoff = m.cutoff || planningDate(chosen);
  return `<form id="replay-form" class="panel"><div class="section-head"><h2>Ustawienia próby</h2>${icon('replay')}</div>
 ${field(
   'Inwestycja do próby',
   `<select id="replay-project" name="project_id">${selectOptions(
     candidates.map((p) => [p.id, p.title]),
     chosen.id
   )}</select>`
 )}
 <div class="tag-gap">${pill(chosen.dataset)}</div>
 ${field('Stan wiedzy na dzień', formInput('cutoff', 'date', cutoff.slice(0, 10), 'required') + '<small>Do prognozy trafią wyłącznie informacje dostępne do końca tego dnia.</small>')}
 ${previewToggle(m.filters)}<button class="button primary" type="submit">${icon('replay')} Rozpocznij próbę</button>${statusLine}</form>`;
}
function filters(mode) {
  const f = modes[mode].filters;
  return `<form class="toolbar" id="comparison-filters" data-mode="${mode}">
 ${field('Grupa porównawcza', `<select name="type">${selectOptions([['', 'Wszystkie typy'], ...sectorTypes(mode === 'analiza' ? modes.analiza.draft : currProject(modes.proba.id)).map((t) => [t, t])], f.type)}</select>`)}
 <label class="check"><input type="checkbox" name="live_operation" ${f.live_operation ? 'checked' : ''}> Tylko obiekty czynne podczas prac</label>
 ${previewToggle(f)}<button type="submit" class="button">${icon('settings')} Zastosuj</button>${statusLine}</form>`;
}
function metricPanel(metrics, schedule) {
  const days = metrics?.actual_days || {},
    points = arr(days.points).filter((p) => p.value != null),
    planned = schedule?.planned_days;
  const max = Math.max(1, Number(planned) || 0, ...points.map((p) => Number(p.value) || 0));
  return `<section class="panel"><div class="section-head"><div><h2>Obrona harmonogramu</h2><p class="hint">Plan i rzeczywisty czas porównywalnych inwestycji w dniach.</p></div>${icon('calendar')}</div>
 ${days.scope === 'contract' ? notice('Zakres porównania: czas umowy na roboty. Harmonogram całej inwestycji może obejmować dodatkowe etapy.', true) : ''}
 <p class="hint">${{ insufficient: 'Za mało danych do oceny planowanego terminu.', above_range: 'Plan przekracza największą zaobserwowaną wartość.', below_range: 'Plan jest krótszy od najkrótszego porównywalnego przypadku.', within_range: 'Plan mieści się w obserwowanym zakresie.' }[schedule?.assessment] || ''}</p>
 <div class="chart-list">${planned > 0 ? `<div class="chart-row target"><span>Twój plan</span><meter aria-label="Planowany czas" min="0" max="${max}" value="${Number(planned)}"></meter><b>${num(planned)} dni</b></div>` : ''}
 ${points.map((p) => `<div class="chart-row"><a href="${projectURL(p.id)}">${text(p.title)}</a><meter aria-label="Rzeczywisty czas" value="${Number(p.value)}" min="0" max="${max}"></meter><b>${num(p.value)} dni</b></div>`).join('')}</div>
 ${!points.length ? empty('W tej grupie brak udokumentowanych rzeczywistych czasów realizacji.') : ''}
 <div class="table-wrap"><table><thead><tr><th>Miara</th><th>Próba</th><th>Min.</th><th>Mediana</th><th>Maks.</th></tr></thead><tbody>
 ${Object.entries(metricLabel)
   .map(([key, title]) => {
     const m = metrics?.[key] || {};
     return `<tr><th scope="row">${title}${m.scope_label ? ' · ' + esc(m.scope_label) : ''}</th><td>${num(m.count ?? 0)}</td><td>${metricValue(m.min, key)}</td><td>${metricValue(m.median, key)}</td><td>${metricValue(m.max, key)}</td></tr>`;
   })
   .join('')}</tbody></table></div>
 <p class="hint">Zakres obejmuje zaobserwowane przypadki. Liczebność dotyczy projektów z danymi dla danej miary.</p></section>`;
}
function scenarioPanel(result, project) {
  const scenario = result.scenario;
  if (!scenario) return '';
  const scope = scenario.scope || project?.metric_scope;
  const scopeLabel = scopes.find(([code]) => code === scope)?.[1] || '';
  const cards = [
    ['cost', 'Koszt po uwzględnieniu odchyleń'],
    ['duration', 'Czas po uwzględnieniu odchyleń'],
  ]
    .map(([key, title]) => {
      const range = scenario[key];
      if (!range || !Number.isFinite(range.low) || !Number.isFinite(range.high)) return '';
      const unit = range.unit === 'PLN' ? 'zł' : range.unit || (key === 'cost' ? 'zł' : 'dni');
      const points = arr(result.metrics?.[range.metric]?.points);
      return `<article class="list-card"><h3>${title}</h3>
      <p><strong>${num(range.low, 2)} – ${num(range.high, 2)} ${esc(unit)}</strong></p>
      <p class="hint">Liczebność próby: ${num(range.count ?? 0, 0)}</p>
      ${points.length ? `<details><summary>Odchylenia w porównywalnych przypadkach</summary>${points.map((p) => `<div><a href="${projectURL(p.id)}">${text(p.title)}</a> · ${metricValue(p.value, range.metric)}${evidence(p.sources)}</div>`).join('')}</details>` : ''}
      </article>`;
    })
    .join('');
  const reasons = [...new Set(arr(scenario.reasons))];
  if (!cards && !reasons.length) return '';
  return `<section class="panel"><div class="section-head"><div><h2>Scenariusz według historycznych odchyleń</h2>
    ${scopeLabel ? `<p class="hint">Zakres danych porównawczych · ${esc(scopeLabel)}</p>` : ''}</div></div><div class="card-list">${cards}</div>${reasons.map((reason) => notice(reason, true)).join('')}</section>`;
}
function flagPanel(result) {
  const flags = arr(result.flags),
    priority = arr(result.checklist).length ? result.checklist : flags.slice(0, 3),
    rest = flags.filter((f) => !priority.some((c) => c.id === f.id));
  const card = (
    f
  ) => `<article class="list-card"><div class="card-head"><h3>${text(f.title || f.category)}</h3>${pill(f.status)}</div><p><b>${text(f.question, '')}</b></p>${f.action ? `<p>${esc(f.action)}</p>` : ''}
 ${arr(f.missing).length ? `<p class="hint">Do uzupełnienia · ${f.missing.map(esc).join(', ')}</p>` : ''}
 ${f.draft_clause?.text ? `<details><summary>Propozycja zapisu do oceny eksperta</summary><p>${esc(f.draft_clause.text)}</p>${f.draft_clause.source ? source(f.draft_clause.source) : ''}</details>` : ''}
 ${f.possible_impact ? `<p class="hint">Możliwy skutek · ${esc(f.possible_impact)}</p>` : ''}${evidence(f.evidence)}
 ${arr(f.answer_evidence).length ? `<details><summary>Fragmenty odpowiadające na pytanie</summary>${evidence(f.answer_evidence)}</details>` : ''}
 ${f.expert_source ? source(f.expert_source) : ''}
 ${arr(f.precedents)
   .map((x) =>
     typeof x === 'object'
       ? `<details><summary>Wcześniejszy przypadek · ${text(x.title || x.project_title || x.id)}</summary>${evidence(x.event?.evidence || x.evidence)}${x.id || x.project_id ? linkBtn(projectURL(x.project_id || x.id), 'Otwórz sprawę', 'folder') : ''}</details>`
       : ''
   )
   .join('')}
 ${result.reviews?.[f.id] ? pill(result.reviews[f.id].status) : ''}${result.analysis_id && writable() ? `<button class="text-button" data-act="analysis-review" data-flag="${esc(f.id)}">${icon('verify')} Oceń wniosek</button>` : ''}</article>`;
  return `<section class="panel"><div class="section-head"><h2>Pytania przed przetargiem</h2><span class="pill">${flags.length}</span></div><div class="card-list">${priority.map(card).join('') || empty('W przekazanym materiale nie znaleziono podstaw do wskazania pytań z katalogu.')}</div>${rest.length ? `<details><summary>Pozostałe wnioski (${rest.length})</summary><div class="card-list">${rest.map(card).join('')}</div></details>` : ''}</section>`;
}
function sectorChecks(r) {
  if (!arr(r.water_supply_checklist).length) return '';
  return `<section class="panel"><h2>Lista kontrolna sieci wodociągowej</h2>${r.water_supply_checklist.map((c) => `<details><summary>${text(c.title)}</summary><p class="hint">${c.status === 'fragment_do_oceny' ? 'Znaleziono fragment do oceny' : 'Brak fragmentu w dokumentacji'}</p>${evidence(c.evidence)}${c.expert_source ? source(c.expert_source) : ''}</details>`).join('')}</section>`;
}
function comparablePanel(result) {
  return `<section class="panel"><div class="section-head"><h2>Podobne inwestycje</h2><span class="pill">${arr(result.comparables).length}</span></div><div class="card-list">${
    arr(result.comparables)
      .map(
        (c) => `<article class="list-card">
 <div class="card-head"><a class="title" href="${projectURL(c.id)}">${text(c.title)}</a><span class="pill blue">${num(c.score)} / 100</span></div>
 <p class="hint">${arr(c.reasons).map(esc).join(' · ')}</p><details><summary>Dane porównawcze i źródła</summary><p class="hint">${text(c.metric_scope_label, '')}</p><dl class="detail-grid"><div><dt>Koszt planowany</dt><dd>${money(c.metrics?.planned_cost)}</dd></div><div><dt>Koszt końcowy</dt><dd>${money(c.metrics?.actual_cost)}</dd></div><div><dt>Czas rzeczywisty</dt><dd>${metricValue(c.metrics?.actual_days, 'actual_days')}</dd></div></dl>${evidence(c.evidence)}</details></article>`
      )
      .join('') || empty('Brak zakończonych inwestycji spełniających warunki porównania.')
  }</div></section>`;
}
function replayPanel(r) {
  const replay = r.replay;
  if (!replay) return '';
  if (!replay.revealed)
    return `<div class="flash"><span class="icon-tile">${icon('lock')}</span><h3>Rzeczywisty przebieg jest zasłonięty</h3><p>Sprawdź pytania i grupę porównawczą. Potem skonfrontuj je z późniejszą dokumentacją.</p><form id="reveal-form"><button class="button primary" type="submit">${icon('replay')} Odsłoń rzeczywisty przebieg</button>${statusLine}</form></div>`;
  return `<section class="panel"><div class="section-head"><h2>Rzeczywisty przebieg</h2>${icon('checkfile')}</div>
 ${[
   ['Potwierdzone kategorie', replay.hits],
   ['Pominięte kategorie', replay.missed],
   ['Sygnały bez potwierdzenia', replay.unconfirmed],
 ]
   .map(
     ([t, v]) =>
       `<div><strong>${t}</strong><p class="hint">${
         arr(v)
           .map((x) => text(typeof x === 'string' ? x : x.title || x.category))
           .join(', ') || 'Brak'
       }</p></div>`
   )
   .join('')}
 <div class="card-list">${
   arr(replay.observed)
     .map((e) => `<div class="list-card"><b>${text(e.title || e.category)}</b>${evidence(e.evidence)}</div>`)
     .join('') || empty('Brak potwierdzonych późniejszych zdarzeń w danych projektu.')
 }</div>${arr(replay.outcome_evidence).length ? `<details><summary>Późniejsze dokumenty źródłowe (${replay.outcome_evidence.length})</summary>${evidence(replay.outcome_evidence)}</details>` : ''}</section>`;
}
function resultView(mode) {
  const m = modes[mode],
    r = m.result;
  if (!r)
    return `<div class="flash"><span class="icon-tile">${icon(mode === 'proba' ? 'replay' : 'analysis')}</span><h2>${mode === 'proba' ? 'Decyzja w warunkach z dnia przetargu' : 'Karta przygotowania inwestycji'}</h2><p>${mode === 'proba' ? 'Wybierz zakończony projekt i datę. Najpierw zobaczysz ocenę opartą na wcześniejszych projektach, następnie dokumentację rzeczywistego przebiegu.' : 'Po analizie zobaczysz pytania do dokumentacji, udokumentowane przypadki porównawcze i zakres zmian kosztu oraz czasu.'}</p></div>`;
  const approval = r.reviews?.all;
  return `<div class="stack"><section class="panel"><div class="section-head"><div><h2>${mode === 'proba' ? 'Ocena przed odsłonięciem' : 'Wynik analizy'}</h2><p class="hint">${approval ? esc(label(approval.status)) + ' · ' + text(approval.actor) + ' · ' + date(approval.at) : 'Propozycja analityczna do oceny eksperta'} · próba: ${num(r.sample_size ?? arr(r.comparables).length)}${r.as_of ? ' · stan na ' + date(r.as_of) : ''}</p></div></div>
 ${approval?.comment ? `<p class="hint">${esc(approval.comment)}</p>` : ''}
 ${filters(mode)}${arr(r.warnings)
   .map((w) => notice(w, true))
   .join('')}
 <div class="actions"><button class="button" data-act="export-analysis" data-mode="${mode}">${icon('download')} Eksport JSON</button>${mode === 'analiza' ? `<button class="button" data-act="export-brief">${icon('file')} Pobierz kartę do Worda</button>${r.analysis_id && writable() ? '<button class="button" data-act="analysis-review">Oceń analizę</button>' : ''}` : ''}</div>${r.analysis_id ? `<a class="text-button" href="#analiza/${encodeURIComponent(r.analysis_id)}">Odnośnik do zapisanej analizy ${icon('link')}</a>` : ''}</section>
 ${mode === 'analiza' ? sensitivityPanel(r) : ''}${mode === 'proba' && r.replay?.revealed ? replayPanel(r) : ''}${flagPanel(r)}${mode === 'proba' && !r.replay?.revealed ? replayPanel(r) : ''}${scenarioPanel(r, mode === 'analiza' ? m.draft : null)}${metricPanel(r.metrics, r.schedule)}${comparablePanel(r)}${sectorChecks(r)}</div>`;
}
export function analysisView(mode) {
  return (
    pagehead(
      mode === 'proba' ? 'Próba generalna' : 'Nowa analiza',
      mode === 'proba'
        ? 'Odtwórz decyzję inwestycyjną przy historycznym stanie wiedzy.'
        : 'Sprawdź plan, harmonogram i dokumentację przed ogłoszeniem przetargu.',
      mode === 'analiza' && (modes.analiza.result || modes.analiza.draft.title || modes.analiza.draft.description)
        ? '<button class="button" data-act="fresh-plan">Nowy plan</button>'
        : ''
    ) +
    `<div class="analysis-layout"><div>${mode === 'analiza' ? analysisForm() : replayForm()}</div><div id="result-view" aria-live="polite">${resultView(mode)}</div></div>`
  );
}
function readDraft(form) {
  const f = new FormData(form),
    p = { ...modes.analiza.draft };
  for (const key of ['title', 'description', 'type']) p[key] = String(f.get(key) || '').trim();
  for (const key of ['planned_days', 'planned_cost']) p[key] = f.get(key) ? Number(f.get(key)) : null;
  p.metric_scope = f.get('metric_scope') === 'contract' ? 'contract' : 'project';
  const selected = sectors().find((s) => s.id === f.get('sector_id'));
  if (selected) {
    p.sector_id = selected.id;
    p.sector = selected.name;
  }
  p.live_operation = f.get('live_operation') === '' ? null : f.get('live_operation') === 'true';
  return p;
}
function renderResult(mode) {
  const el = document.querySelector('#result-view');
  if (el) el.innerHTML = resultView(mode);
}
async function run(mode, reveal = false) {
  const m = modes[mode];
  const body =
    mode === 'analiza'
      ? { project: m.draft, filters: m.filters }
      : {
          project_id: m.id,
          cutoff: m.cutoff,
          filters: m.filters,
          reveal,
          ...(reveal && m.result?.replay_id ? { replay_id: m.result.replay_id } : {}),
        };
  const requestNo = (m.requestNo || 0) + 1;
  m.requestNo = requestNo;
  const r = await api(mode === 'analiza' ? '/api/analyze' : '/api/replay', { method: 'POST', body });
  if (m.requestNo !== requestNo) return;
  m.result = r;
  if (mode === 'analiza' && location.hash.startsWith('#analiza/') && r.analysis_id) {
    window.history.replaceState(null, '', '#analiza/' + encodeURIComponent(r.analysis_id));
  }
  if (location.hash.split('/')[0] === '#' + mode) renderResult(mode);
}
export function useAsDraft(p) {
  modes.analiza.draft = Object.fromEntries(
    [
      'title',
      'description',
      'type',
      'sector',
      'sector_id',
      'planned_days',
      'metric_scope',
      'planned_cost',
      'live_operation',
      'location',
      'buyer',
    ].map((k) => [k, p[k]])
  );
  modes.analiza.draft.documents = [];
  modes.analiza.draft.id = p.id;
  modes.analiza.result = null;
  modes.analiza.filters = {};
  location.hash = 'analiza';
}
export async function restoreAnalysis(id) {
  const saved = await api('/api/analyses/' + encodeURIComponent(id));
  if (location.hash !== '#analiza/' + encodeURIComponent(id)) return;
  Object.assign(modes.analiza, {
    draft: saved.input?.project || {},
    filters: saved.input?.filters || {},
    result: { ...saved.result, analysis_id: id, reviews: saved.reviews || {} },
  });
}
export function handleAnalysisChange(e) {
  changeSensitivity(e.target, modes.analiza.result);
  if (e.target.form?.id === 'analysis-form' && e.target.name === 'sector_id') {
    const form = e.target.form,
      s = sectors().find((i) => i.id === e.target.value);
    form.elements.type.value = '';
    form.querySelector('#project-types').innerHTML = arr(s?.types)
      .map((t) => `<option value="${esc(t.name)}"></option>`)
      .join('');
    form.querySelector('#selected-sector-description').textContent = s?.description || '';
    modes.analiza.draft = readDraft(form);
    delete modes.analiza.filters.type;
  }
  if (e.target.form?.id === 'replay-form') {
    const m = modes.proba;
    m.requestNo = (m.requestNo || 0) + 1;
    m.result = null;
    if (e.target.name === 'cutoff') m.cutoff = e.target.value;
    if (e.target.name === 'preview_links') m.filters.preview_links = e.target.checked;
    renderResult('proba');
  }
  if (e.target.id === 'replay-project') {
    const m = modes.proba,
      p = currProject(e.target.value);
    m.id = e.target.value;
    m.cutoff = planningDate(p).slice(0, 10);
    m.result = null;
    document.querySelector('main').innerHTML = analysisView('proba');
  }
}
export function handleDraftInput(e) {
  if (e.target.form?.id === 'analysis-form') e.target.form.querySelector('[data-act="example-plan"]')?.remove();
  if (e.target.form?.id !== 'analysis-form' || e.target.type === 'file') return;
  const m = modes.analiza;
  m.draft = readDraft(e.target.form);
  m.requestNo = (m.requestNo || 0) + 1;
  if (m.result) {
    m.result = null;
    renderResult('analiza');
  }
}
function documentsFrom(records, file) {
  return records.flatMap((r) => {
    if (arr(r.documents).length) return r.documents;
    const t = r.text || r.description || r.excerpt || (r.kind === 'project' ? r.title : '');
    return t
      ? [
          {
            title: r.title || file.name,
            text: t,
            source: r.source?.name || file.name,
            locator: r.locator || r.source?.locator || '',
            published_at: r.published_at || null,
          },
        ]
      : [];
  });
}
export function handleAnalysisSubmit(e) {
  const form = e.target,
    mode = form.dataset.mode;
  if (
    !['analysis-form', 'analysis-review-form', 'replay-form', 'comparison-filters', 'reveal-form'].includes(
      form.id
    )
  )
    return false;
  e.preventDefault();
  submitTask(form, async () => {
    if (form.id === 'analysis-review-form') {
      const m = modes.analiza,
        r = m.result,
        data = new FormData(form);
      if (r?.analysis_id !== form.dataset.id) throw new Error('Otwórz ponownie wynik analizy.');
      const target = form.dataset.flag || 'all';
      const url = '/api/analyses/' + encodeURIComponent(r.analysis_id);
      let assessment;
      try {
        assessment = await api(url + '/review', {
          method: 'POST',
          body: {
            decision: data.get('decision'), comment: data.get('comment'),
            flag_id: target, expected_at: r.reviews?.[target]?.at ?? null,
          },
        });
      } catch (error) {
        if (error.status !== 409) throw error;
        const saved = await api(url);
        r.reviews = saved.reviews || {};
        renderResult('analiza');
        const current = r.reviews[target];
        throw new Error(`Ocena zmieniła się. Aktualna decyzja: ${label(current.status)} (${current.actor}). ${current.comment || ''} Sprawdź ją przed ponownym zapisem.`);
      }
      r.reviews = { ...r.reviews, [target]: assessment };
      closeDialog();
      renderResult('analiza');
      toast('Zapisano ocenę eksperta.');
    } else if (form.id === 'analysis-form') {
      const p = readDraft(form);
      p.documents = [...arr(p.documents)];
      if (!p.title && !p.description && !p.documents.length && !form.elements.attachment.files.length)
        throw new Error('Podaj opis inwestycji lub dołącz dokument.');
      for (const file of form.elements.attachment.files) {
        const upload = new FormData();
        upload.set('file', file);
        const r = await api('/api/parse', { method: 'POST', body: upload });
        const docs = documentsFrom(arr(r.records), file);
        if (!docs.length) throw new Error('Brak możliwego do odczytania tekstu w pliku ' + file.name + '.');
        p.documents.push(...docs);
      }
      modes.analiza.draft = p;
      modes.analiza.filters.preview_links = form.elements.preview_links.checked;
      form.elements.attachment.value = '';
      await run('analiza');
      if (form.isConnected) {
        form.outerHTML = analysisForm();
      }
    } else if (form.id === 'replay-form') {
      const f = new FormData(form);
      Object.assign(modes.proba, {
        id: f.get('project_id'),
        cutoff: f.get('cutoff'),
        filters: { preview_links: f.has('preview_links') },
      });
      await run('proba');
    } else if (form.id === 'reveal-form') {
      await run('proba', true);
    } else {
      const f = new FormData(form);
      modes[mode].filters = { preview_links: f.has('preview_links') };
      const mainToggle = document.querySelector(
        mode === 'analiza' ? '#analysis-form [name=preview_links]' : '#replay-form [name=preview_links]'
      );
      if (mainToggle) mainToggle.checked = f.has('preview_links');
      if (f.get('type')) modes[mode].filters.type = f.get('type');
      if (f.get('live_operation')) modes[mode].filters.live_operation = true;
      await run(mode, false);
    }
  });
  return true;
}
export async function handleAnalysisAction(action, btn) {
  if (action === 'example-plan') {
    const form = btn.closest('form');
    form.elements.title.value = 'Przykład · budowa kanalizacji sanitarnej z przepompownią';
    form.elements.description.value = 'Gmina planuje budowę kanalizacji sanitarnej z przepompownią. Na trasie występują kolizje z uzbrojeniem i wysoki poziom wód gruntowych. Wstępny harmonogram zakłada 365 dni.';
    form.elements.type.value = 'Sieć kanalizacji sanitarnej';
    form.elements.planned_cost.value = '5000000';
    form.elements.planned_days.value = '365';
    form.elements.metric_scope.value = 'contract';
    form.elements.preview_links.checked = true;
    btn.remove();
    form.requestSubmit();
    return true;
  }
  if (action === 'fresh-plan') {
    modes.analiza = { draft: {}, filters: {}, result: null };
    if (location.hash !== '#analiza') location.hash = 'analiza';
    else document.querySelector('main').innerHTML = analysisView('analiza');
    return true;
  }
  if (action === 'analysis-review') {
    const r = modes.analiza.result,
      flag = btn.dataset.flag;
    dialog(
      flag ? 'Ocena wniosku' : 'Ocena zapisanej analizy',
      `<form id="analysis-review-form" data-id="${esc(r.analysis_id)}" data-flag="${esc(flag)}">${flag ? `<p class="title">${text(arr(r.flags).find((f) => f.id === flag)?.title)}</p>` : ''}${r.preview_links ? notice('Aby zatwierdzić analizę, zweryfikuj powiązania i przelicz wynik z wyłączonym podglądem.', true) : ''}${field('Decyzja', `<select name="decision">${r.preview_links ? '' : '<option value="accepted">Zatwierdź</option>'}<option value="rejected">Odrzuć</option></select>`)}${field('Komentarz eksperta', '<textarea name="comment" rows="3" maxlength="4000"></textarea>')}<button class="button primary" type="submit">Zapisz decyzję</button>${statusLine}</form>`
    );
    return true;
  }
  if (action === 'export-analysis') {
    await saveBlob(modes[btn.dataset.mode].result, 'risk-miner-analiza.json');
    return true;
  }
  if (action === 'export-brief') {
    btn.disabled = true;
    try {
      const m = modes.analiza;
      const res = await request('/api/brief', {
        method: 'POST',
        body: { project: m.draft, filters: m.filters, analysis_id: m.result?.analysis_id, sensitivity_selection: m.result?.sensitivity_selection },
      });
      await saveBlob(await res.blob(), 'risk-miner-karta.docx');
      toast('Pobrano kartę inwestycji.');
    } finally {
      btn.disabled = false;
    }
    return true;
  }
  if (action === 'remove-doc') {
    const f = document.querySelector('#analysis-form');
    modes.analiza.draft = readDraft(f);
    modes.analiza.draft.documents.splice(Number(btn.dataset.index), 1);
    modes.analiza.result = null;
    f.outerHTML = analysisForm();
    renderResult('analiza');
    return true;
  }
  return false;
}
