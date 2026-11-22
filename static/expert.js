import {
  api,
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
  pagehead,
  pill,
  projectURL,
  recordDetails,
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
import { sectorAction, sectorPanel, sectorRuleFields, sectorSubmit, sectors } from './sectors.js';

const panels = { status: 'pending', project: '', kind: '', limit: 35 };
const kinds = {
  observations: 'Powiązanie ze źródłem',
  events: 'Zdarzenie lub sygnał',
  measurements: 'Pomiar',
  changes: 'Zmiana umowy',
  contracts: 'Kontrakt',
  procedures: 'Postępowanie',
  documents: 'Dokument',
  findings: 'Wniosek',
  categories: 'Kategoria',
};
export const kindLabel = (s) => kinds[s] || label(s);
export function resetExperts() {
  panels.status = 'pending';
  panels.project = '';
  panels.kind = '';
  panels.limit = 35;
}
function reviewRows() {
  const list = store.reviews.filter(
    (x) =>
      (!panels.status || x.status === panels.status) &&
      (!panels.project || x.project_id === panels.project) &&
      (!panels.kind || x.kind === panels.kind)
  );
  return `<div class="section-head"><h2>Kolejka decyzji</h2><span class="pill">${list.length}</span></div>${
    list
      .slice(0, panels.limit)
      .map((x) => {
        const p = currProject(x.project_id);
        return `<button class="review-row feed-row" data-act="review" data-id="${esc(x.id)}"><span class="icon-tile tone-orange">${icon('verify')}</span><span class="grow"><span class="title">${text(x.title || kindLabel(x.kind))}</span><span class="sub">${esc(kindLabel(x.kind))} · ${text(p?.title || x.project_id)}</span></span>${pill(x.status)}${icon('next')}</button>`;
      })
      .join('') || empty('Nie ma decyzji spełniających wybrane kryteria.')
  }${list.length > panels.limit ? '<button class="button" data-act="more-reviews">Pokaż kolejne</button>' : ''}`;
}
export function reviewView(pid) {
  if (pid) panels.project = pid;
  return (
    pagehead('Panel eksperta', 'Sprawdź podstawę powiązania lub wniosku, zanim trafi do kolejnych analiz.') +
    `<div class="panel"><form id="review-filter" class="toolbar">
 ${field(
   'Status',
   `<select name="status">${selectOptions(
     [
       ['', 'Wszystkie decyzje'],
       ['pending', 'Do weryfikacji'],
       ['accepted', 'Zatwierdzone'],
       ['corrected', 'Skorygowane'],
       ['rejected', 'Odrzucone'],
     ],
     panels.status
   )}</select>`
 )}
 ${field('Inwestycja', `<select name="project">${selectOptions([['', 'Wszystkie inwestycje'], ...store.projects.map((p) => [p.id, p.title])], panels.project)}</select>`)}
 ${field('Rodzaj', `<select name="kind">${selectOptions([['', 'Wszystkie rodzaje'], ...[...new Set(store.reviews.map((x) => x.kind))].map((k) => [k, kindLabel(k)])], panels.kind)}</select>`)}</form><div id="review-rows">${reviewRows()}</div></div>`
  );
}
export function reviewModal(id) {
  const r = store.reviews.find((x) => x.id === id);
  if (!r) return toast('Nie znaleziono decyzji.');
  const p = currProject(r.project_id),
    data = r.payload || {};
  const src = arr(p?.documents).find((x) => x.id === r.source_id);
  dialog(
    'Weryfikacja rekordu',
    `<p class="hint">${esc(kindLabel(r.kind))} · ${text(p?.title)}</p><h3>${text(r.title || kindLabel(r.kind))}</h3><div class="tag-gap">${pill(r.status)}${pill(p?.dataset)}</div>
 ${r.technical_assessment ? `<section class="notice"><strong>Weryfikacja techniczna AI · ${esc(({accepted:'propozycja przyjęcia',corrected:'propozycja korekty',rejected:'propozycja odrzucenia',pending:'do dalszej oceny'})[r.technical_assessment])}</strong><p>${esc(r.technical_comment)}</p></section>` : ''}
 ${r.actor && (!r.technical_assessment || r.status !== 'pending') ? `<section class="notice"><strong>Ostatni wpis · ${esc(r.actor)}</strong>${r.comment ? `<p>${esc(r.comment)}</p>` : ''}</section>` : ''}
 ${data.description || data.reason || data.match_reason ? `<p>${text(data.description || data.reason || data.match_reason)}</p>` : ''}
 ${arr(data.reasons).length ? `<p class="hint"><b>Podstawa dopasowania</b> · ${data.reasons.map(esc).join(' · ')}</p>` : ''}
 ${data.confidence != null ? `<p class="hint">Wskaźnik dopasowania: ${esc(data.confidence)}.</p>` : ''}
 ${data.fact_type === 'proposed' ? notice('Wartość wnioskowana w dokumencie. Zatwierdzenie potwierdza treść wniosku, a skuteczność zmiany wymaga odrębnego dowodu.') : ''}
 ${data.value != null ? `<strong>${esc(data.value)} ${text(data.unit, '')}</strong>` : ''}
 ${data.excerpt ? `<blockquote>${esc(data.excerpt)}</blockquote>` : ''}${src ? source(src, p) : data.evidence?.length ? data.evidence.map((d) => source(d, p)).join('') : notice('W rekordzie brak połączenia z dokumentem źródłowym.', true)}
 ${recordDetails(data)}<hr>${
   writable()
     ? `<form id="review-form" data-id="${esc(id)}">
 ${field('Decyzja', `<select name="decision"><option value="accepted">Zatwierdź</option><option value="corrected">Skoryguj i zatwierdź</option><option value="rejected">Odrzuć</option></select>`)}
 <div id="review-correction" hidden>${field('Tytuł rekordu', `<input name="title" value="${esc(data.title || r.title)}">`)}
 ${arr(p?.contracts).length ? field('Przypisany kontrakt', `<select name="contract_id">${selectOptions([['', 'Bez przypisania'], ...p.contracts.map((c) => [c.id, c.title || c.id])], data.contract_id)}</select>`) : ''}
 ${field('Kategoria zdarzenia', `<input name="category" list="categories" value="${esc(data.category)}"><datalist id="categories">${store.catalog.map((c) => `<option value="${esc(c.category || c.id)}">${text(c.title)}</option>`).join('')}</datalist>`)}
 ${data.value != null ? field('Wartość pomiaru', `<input name="value" value="${esc(data.value)}">`) : ''}
 </div>${field('Uzasadnienie decyzji', `<textarea name="comment" rows="2" maxlength="4000" placeholder="Wskaż ustalenie lub powód korekty"></textarea>`)}
 <button class="button primary" type="submit">${icon('check')} Zapisz decyzję</button>${statusLine}</form>`
     : notice('Twoja rola umożliwia przegląd decyzji eksperckich.')
 }`
  );
}
const ruleId = (r) => String(r.id || r.category || '');
function catalogProposals() {
  const proposals = arr(store.category_proposals);
  if (!proposals.length) return '';
  return `<section class="panel"><h2>Proponowane kategorie</h2><div class="card-list">${proposals
    .map(
      (
        p
      ) => `<article class="list-card"><div class="card-head"><strong>${text(p.title)}</strong>${pill(p.status)}</div><p>${text(p.question, '')}</p><p class="hint">${text(p.reason, '')}</p>${
        p.source_id
          ? source(
              p.source_id,
              store.projects.find((c) => arr(c.documents).some((d) => d.id === p.source_id))
            )
          : ''
      }
 ${store.auth.role === 'admin' && p.status === 'pending' ? `<form class="actions" id="proposal-${esc(p.id)}" data-proposal="${esc(p.id)}"><button class="button" type="submit" value="accepted">${icon('check')} Zatwierdź kategorię</button><button class="button danger" type="submit" value="rejected">Odrzuć</button>${statusLine}</form>` : ''}</article>`
    )
    .join('')}</div></section>`;
}
export function catalogView() {
  return (
    pagehead(
      'Katalog ekspercki',
      'Reguły wykorzystywane do identyfikacji dokumentowanych zdarzeń i pytań przed przetargiem.',
      (writable() ? '<button class="button" data-act="propose-category">Zaproponuj kategorię</button>' : '') +
        (store.auth.role === 'admin'
          ? `<button class="button primary" data-act="rule-new">${icon('plus')} Dodaj regułę</button>`
          : '')
    ) +
    `<div class="stack">${catalogProposals()}${sectorPanel()}<div class="panel"><div class="section-head"><h2>Reguły analizy</h2><span class="pill">${store.catalog.length}</span></div><div class="card-list">
 ${
   store.catalog
     .map(
       (r) =>
         `<article class="list-card"><div class="card-head"><div><span class="eyebrow">${esc(ruleId(r))}</span><h3>${text(r.title)}</h3></div>${store.auth.role === 'admin' ? `<button class="ghost square" data-act="rule" data-id="${esc(ruleId(r))}" aria-label="Edytuj regułę ${esc(ruleId(r))}">${icon('edit')}</button>` : ''}</div><p>${text(r.question, '')}</p><div class="meta"><span class="pill ${r.enabled === false ? '' : 'positive'}">${r.enabled === false ? 'Wyłączona' : 'Aktywna'}</span></div><details><summary>Sygnały i działania</summary><p class="hint">${arr(
           r.signals || r.keywords
         )
           .map(esc)
           .join(
             ' · '
           )}</p><p>${text(r.action, '')}</p>${r.expert_source ? source(r.expert_source) : ''}</details></article>`
     )
     .join('') || empty('Brak reguł w katalogu.')
 }</div></div></div>`
  );
}
function ruleModal(id) {
  const r = store.catalog.find((x) => ruleId(x) === id) || {};
  dialog(
    id ? 'Edytuj regułę' : 'Nowa reguła',
    `<form id="rule-form" data-id="${esc(id)}">${field('Identyfikator', `<input name="id" required ${id ? 'readonly' : ''} maxlength="80" value="${esc(ruleId(r))}">`)}
 ${field('Nazwa', `<input name="title" required maxlength="500" value="${esc(r.title)}">`)}
 ${sectorRuleFields(r)}
 ${field('Sygnały (jeden w wierszu)', `<textarea name="signals" required rows="3">${esc(arr(r.signals || r.keywords).join('\n'))}</textarea>`)}
 ${field('Pytanie do dokumentacji', `<textarea name="question" required rows="2">${esc(r.question)}</textarea>`)}
 ${field('Zalecane działanie', `<textarea name="action" required rows="2">${esc(r.action)}</textarea>`)}
 ${field('Możliwy skutek', `<input name="possible_impact" value="${esc(r.possible_impact)}">`)}
 ${field('Proponowany zapis umowny', `<textarea rows="2" name="draft_clause">${esc(r.draft_clause?.text || r.draft_clause || '')}</textarea>`)}
 <label class="check"><input type="checkbox" name="enabled" ${r.enabled !== false ? 'checked' : ''}> Używaj w kolejnych analizach</label>
 <details><summary>Warunki uznania odpowiedzi za udokumentowaną</summary>${field('Lista warunków (JSON)', `<textarea class="code-field" name="checks" rows="5">${esc(JSON.stringify(r.checks || [], null, 2))}</textarea>`)}</details>
 <div class="actions"><button class="button primary" type="submit">${icon('check')} Zapisz regułę</button></div>${statusLine}</form>`
  );
}
export function auditView() {
  return (
    pagehead('Historia operacji', 'Chronologiczny rejestr importów, zmian i decyzji eksperckich.') +
    `<div class="panel"><div class="table-wrap"><table><thead><tr><th>Data</th><th>Operacja</th><th>Użytkownik</th><th>Szczegóły</th></tr></thead><tbody>${store.audit
      .map(
        (a) =>
          `<tr><td>${text(
            String(a.at || a.created_at || '')
              .replace('T', ' ')
              .slice(0, 19)
          )} UTC</td><td>${text(auditLabel(a.action))}</td><td>${text(a.actor)}</td><td>${recordDetails(a.detail || a)}</td></tr>`
      )
      .join('')}</tbody></table></div>${!store.audit.length ? empty('Brak zarejestrowanych operacji.') : ''}</div>`
  );
}
export const auditLabel = (a) =>
  ({
    import: 'Import danych',
    enrich: 'Wzbogacenie projektu',
    review: 'Weryfikacja rekordu',
    defer_review: 'Skierowanie do oceny branżowej',
    technical_review: 'Ocena techniczna AI',
    catalog: 'Zmiana katalogu',
    analyze: 'Analiza inwestycji',
    seed: 'Inicjalizacja bazy',
    project_edit: 'Edycja projektu',
    analyze_project: 'Analiza projektu',
    replay: 'Próba generalna',
  })[a] || a;
const jobNames = {
  queued: 'W kolejce',
  running: 'W toku',
  done: 'Zakończono',
  partial: 'Zakończono częściowo',
  failed: 'Niepowodzenie',
};
function jobsView() {
  const jobs = arr(store.jobs);
  if (!jobs.length) return '';
  return `<section class="panel"><div class="section-head"><h2>Wzbogacanie w tle</h2><span class="pill">${jobs.length}</span></div><div class="card-list">${jobs
    .slice(0, 12)
    .map(
      (j) =>
        `<div class="list-card"><div class="card-head"><strong>${text(jobNames[j.status] || j.status)}</strong><span class="pill">${text(j.finished, 0)} / ${text(j.total, 0)}</span></div><button class="text-button" data-act="job" data-id="${esc(j.id)}">${icon('refresh')} Odśwież postęp</button></div>`
    )
    .join('')}</div></section>`;
}
async function jobDetail(id) {
  const j = await api('/api/jobs/' + encodeURIComponent(id));
  const existing = arr(store.jobs).find((x) => x.id === id);
  if (existing) Object.assign(existing, j);
  const jobs = document.querySelector('#import-jobs');
  if (jobs) jobs.innerHTML = jobsView();
  dialog(
    'Postęp wzbogacania',
    `<p><b>${text(jobNames[j.status] || j.status)}</b> · zakończone inwestycje ${text(j.finished, 0)} z ${text(j.total, 0)}.</p><div class="actions"><button class="button" data-act="job" data-id="${esc(id)}">${icon('refresh')} Odśwież postęp</button></div><hr><div class="card-list">${arr(
      j.items
    )
      .map(
        (i) =>
          `<article class="list-card"><strong>${text(currProject(i.project_id)?.title || i.project_id)}</strong><p class="hint">${text(jobNames[i.status] || i.status)} · znaleziono ${text(i.found, 0)}, dodano ${text(i.added, 0)}</p>${i.error ? notice(i.error, true) : ''}${arr(
            i.warnings
          )
            .map((w) => notice(w, true))
            .join('')}</article>`
      )
      .join('')}</div>`
  );
}
export function importView(pid) {
  if (!writable())
    return pagehead('Import danych') + notice('Import danych wymaga dostępu eksperta lub administratora.');
  return (
    pagehead('Import danych', 'Dodaj projekty z arkusza lub dołącz dokumentację do istniejącej inwestycji.') +
    `<div class="columns"><form id="import-form" class="panel"><h2>Plik źródłowy</h2>
 ${field('Wybierz plik', `<input type="file" name="file" required accept=".xls,.xlsx,.csv,.tsv,.docx,.doc,.pdf,.txt"><small>Arkusze XLS, XLSX, CSV i TSV oraz dokumenty DOC, DOCX, PDF i TXT.</small>`)}
 ${field('Powiąż dokument z inwestycją', `<select name="project_id">${selectOptions([['', 'Rozpoznaj automatycznie'], ...store.projects.map((p) => [p.id, p.title])], pid)}</select><small>Przy imporcie arkusza wybierz automatyczne rozpoznanie.</small>`)}
 <label class="check"><input type="checkbox" name="enrich" value="true"> Wyszukaj powiązane dane w źródłach publicznych</label>
 <button class="button primary" type="submit">${icon('upload')} Importuj plik</button>${statusLine}</form><div class="stack"><div id="import-result" aria-live="polite"><div class="flash"><span class="icon-tile">${icon('link')}</span><h2>Ślad od pliku do decyzji</h2><p>Każdy rozpoznany fragment otrzyma odsyłacz do źródła. Propozycje powiązań i zdarzeń znajdziesz w panelu eksperta.</p></div></div><div id="import-jobs">${jobsView()}</div></div></div>`
  );
}
export function handleExpertChange(e) {
  const f = e.target.form;
  if (f?.id === 'review-filter') {
    Object.assign(panels, Object.fromEntries(new FormData(f)), { limit: 35 });
    document.querySelector('#review-rows').innerHTML = reviewRows();
  }
  if (f?.id === 'review-form' && e.target.name === 'decision') {
    f.querySelector('#review-correction').hidden = e.target.value !== 'corrected';
    f.elements.comment.required = e.target.value !== 'accepted';
  }
}
export function handleExpertAction(action, b) {
  if (sectorAction(action, b)) return true;
  if (action === 'propose-category') {
    dialog(
      'Propozycja kategorii',
      `<form id="propose-category-form">${field('Nazwa kategorii', '<input name="title" required maxlength="400">')}${field('Pytanie przed przetargiem', '<textarea rows="2" name="question" required></textarea>')}${field('Sygnały do wyszukania (jeden w wierszu)', '<textarea rows="3" name="signals" required></textarea>')}${field('Uzasadnienie', '<textarea rows="2" name="reason" required></textarea>')}${field('Źródło propozycji', `<select name="source_id">${selectOptions([['', 'Bez wskazania'], ...store.projects.flatMap((p) => arr(p.documents).map((d) => [d.id, [p.location, d.title, d.locator].filter(Boolean).join(' · ')]))], '')}</select>`)}<button class="button primary" type="submit">Przekaż do oceny</button>${statusLine}</form>`
    );
    return true;
  }
  if (action === 'job') {
    b.disabled = true;
    jobDetail(b.dataset.id)
      .catch((e) => toast(e.message))
      .finally(() => {
        b.disabled = false;
      });
    return true;
  }
  if (action === 'review') {
    reviewModal(b.dataset.id);
    return true;
  }
  if (action === 'more-reviews') {
    panels.limit += 35;
    document.querySelector('#review-rows').innerHTML = reviewRows();
    return true;
  }
  if (action === 'rule' || action === 'rule-new') {
    ruleModal(b.dataset.id || '');
    return true;
  }
  return false;
}
export function handleExpertSubmit(e, repaint) {
  if (sectorSubmit(e, repaint)) return true;
  const f = e.target;
  const formId = f.getAttribute('id');
  if (
    !['import-form', 'review-form', 'rule-form', 'review-filter', 'propose-category-form'].includes(formId) &&
    !f.dataset.proposal
  )
    return false;
  e.preventDefault();
  if (f.id === 'review-filter') return true;
  submitTask(f, async () => {
    const d = new FormData(f);
    if (f.id === 'propose-category-form') {
      const body = Object.fromEntries(d);
      body.signals = String(body.signals)
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);
      if (!body.source_id) delete body.source_id;
      await api('/api/catalog/proposals', { method: 'POST', body });
      await sync();
      closeDialog();
      repaint();
      toast('Przekazano kategorię do akceptacji.');
      return;
    }
    if (f.dataset.proposal) {
      await api('/api/catalog/proposals/' + encodeURIComponent(f.dataset.proposal), {
        method: 'POST',
        body: { decision: e.submitter.value },
      });
      await sync();
      repaint();
      toast('Zapisano decyzję o kategorii.');
      return;
    }
    if (f.id === 'import-form') {
      if (!d.get('project_id')) d.delete('project_id');
      d.set('enrich', d.get('enrich') ? 'true' : 'false');
      const r = await api('/api/import', { method: 'POST', body: d });
      await sync();
      const dst = document.querySelector('#import-result');
      if (dst)
        dst.innerHTML = `<section class="panel"><div class="section-head"><h2>Import zakończony</h2>${icon('checkfile')}</div><p>Odczytane rekordy: ${text(r.records)}. Inwestycje: ${text(r.projects)}.</p>${r.job_id ? `<p>Wzbogacanie uruchomiono w tle.</p><button class="button" data-act="job" data-id="${esc(r.job_id)}">${icon('refresh')} Odśwież postęp</button>` : ''}${arr(
          r.warnings
        )
          .map((w) => notice(w, true))
          .join('')}<div class="card-list">${arr(r.project_ids)
          .map((id) => linkBtn(projectURL(id), currProject(id)?.title || id, 'folder'))
          .join('')}</div><hr>${linkBtn('#ekspert', 'Otwórz panel eksperta', 'verify')}</section>`;
      const jobs = document.querySelector('#import-jobs');
      if (jobs) jobs.innerHTML = jobsView();
      toast('Zapisano dane źródłowe.');
      return;
    }
    if (f.id === 'review-form') {
      const r = store.reviews.find((x) => x.id === f.dataset.id),
        patch = {};
      if (d.get('decision') === 'corrected') {
        for (const k of ['title', 'category', 'contract_id', 'value']) {
          if (!d.has(k)) continue;
          let val = String(d.get(k)).trim();
          if (val !== String(r.payload?.[k] ?? '')) {
            patch[k] = k === 'value' && typeof r.payload?.value === 'number' ? Number(val) : val || null;
          }
        }
      }
      await api('/api/reviews/' + encodeURIComponent(r.id), {
        method: 'POST',
        body: { decision: d.get('decision'), comment: d.get('comment'), patch, version: r.version },
      });
      await sync();
      closeDialog();
      repaint();
      toast('Zapisano decyzję i jej historię.');
      return;
    }
    const id = String(d.get('id')).trim(),
      existing = store.catalog.find((r) => ruleId(r) === id);
    if (existing && !f.dataset.id) throw new Error('Identyfikator musi być unikalny.');
    let checks;
    try {
      checks = JSON.parse(d.get('checks'));
    } catch {
      throw new Error('Warunki muszą być prawidłową listą JSON.');
    }
    if (
      !Array.isArray(checks) ||
      checks.some(
        (x) =>
          !x ||
          typeof x.label !== 'string' ||
          !Array.isArray(x.terms) ||
          !x.terms.every((t) => typeof t === 'string')
      )
    )
      throw new Error('Każdy warunek wymaga pola label oraz listy terms.');
    const rule = {
      ...existing,
      id,
      category: existing?.category || id,
      title: String(d.get('title')).trim(),
      question: String(d.get('question')).trim(),
      action: String(d.get('action')).trim(),
      possible_impact: d.get('possible_impact'),
      draft_clause: d.get('draft_clause'),
      enabled: d.has('enabled'),
      signals: String(d.get('signals'))
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      checks,
    };
    if (sectors().length) {
      rule.sector_ids = d.getAll('sector_ids');
      if (!rule.sector_ids.length) throw new Error('Wybierz przynajmniej jeden sektor stosowania reguły.');
    }
    rule.draft_clause = {
      ...(existing?.draft_clause && typeof existing.draft_clause === 'object' ? existing.draft_clause : {}),
      text: String(d.get('draft_clause') || ''),
      status: 'do opracowania przez eksperta',
    };
    const rules = existing ? store.catalog.map((r) => (r === existing ? rule : r)) : [...store.catalog, rule];
    await api('/api/catalog', { method: 'PUT', body: { rules } });
    await sync();
    closeDialog();
    repaint();
    toast('Zaktualizowano katalog.');
  });
  return true;
}
