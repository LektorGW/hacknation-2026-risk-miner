import { arr, esc, evidence, field, num, projectURL, selectOptions } from './lib.js';

const titles = { duration: 'Termin', cost: 'Koszt' };

function row(label, interval, base, unit, alternate = false) {
  const width = base.high - base.low;
  const left = width ? (100 * (interval.low - base.low)) / width : 50;
  const right = width ? (100 * (base.high - interval.high)) / width : 50;
  return `<div class="range-row"><div><span>${label} · n = ${interval.count}</span>
    <strong>${num(interval.low, 2)} – ${num(interval.high, 2)} ${unit}</strong></div>
    <div class="range-track" aria-hidden="true"><i class="${alternate ? 'alternate' : ''}" style="left:${left}%;right:${right}%"></i></div></div>`;
}

export function sensitivityPanel(result) {
  const available = Object.keys(titles).filter((k) => result.scenario?.[k]?.without_one?.length);
  if (!available.length) return '';
  const selection = result.sensitivity_selection;
  const metric = available.includes(selection?.metric) ? selection.metric : available[0];
  const base = result.scenario[metric], variants = base.without_one;
  const points = new Map(arr(result.metrics[base.metric].points).map((p) => [p.id, p]));
  const variant = variants.find((v) => v.omitted_id === selection?.omitted_id) || variants[0];
  const point = points.get(variant.omitted_id);
  const unit = metric === 'cost' ? 'zł' : 'dni';
  const shifts = [];
  if (variant.low !== null) {
    if (variant.low > base.low) shifts.push(`Dolna granica rośnie o ${num(variant.low - base.low, 2)} ${unit}.`);
    if (variant.high < base.high) shifts.push(`Górna granica maleje o ${num(base.high - variant.high, 2)} ${unit}.`);
    if (!shifts.length) shifts.push('Obie granice pozostają takie same.');
  }
  return `<section class="panel sensitivity" id="sensitivity-panel"><div class="section-head"><div>
    <h2>Co zmienia jedna inwestycja?</h2><p class="hint">Porównaj przedział dla całej grupy z wynikiem po pominięciu jednego projektu. Na początek wybrano przypadek o największym wpływie na szerokość przedziału.</p></div></div>
    ${result.preview_links ? '<p class="hint">W tym obliczeniu włączono roboczy podgląd powiązań po identyfikatorach.</p>' : ''}
    <div class="sensitivity-controls">${field('Porównywana miara', `<select id="sensitivity-metric">${selectOptions(available.map((k) => [k,titles[k]]), metric)}</select>`)}
    ${field('Pomiń w porównaniu', `<select id="sensitivity-case">${selectOptions(variants.map((v) => [v.omitted_id, points.get(v.omitted_id).title]), variant.omitted_id)}</select>`)}</div>
    ${row('Pełna grupa', base, base, unit)}
    ${variant.low === null ? `<p class="notice">Pozostały ${variant.count} obserwacje. Do wyznaczenia przedziału potrzebne są co najmniej trzy.</p>` : row('Po pominięciu', variant, base, unit, true)}
    ${shifts.length ? `<p class="range-change" aria-live="polite">${shifts.join(' ')}</p>` : ''}
    <details><summary>Skąd pochodzi pomiar pominiętego projektu?</summary><p><a href="${projectURL(point.id)}">${esc(point.title)}</a></p>
    <p>Odchylenie w źródłach: <strong>${num(point.value, 2)} ${metric === 'cost' ? '%' : 'dni'}</strong></p>${evidence(point.sources)}</details>
    <p class="hint">Oba zakresy wynikają z historycznych odchyleń dla tej samej podstawy porównania. Pominięcie projektu służy wyłącznie sprawdzeniu wyniku.</p></section>`;
}

export function changeSensitivity(target, result) {
  if (!result || !['sensitivity-metric', 'sensitivity-case'].includes(target.id)) return;
  const metric = document.querySelector('#sensitivity-metric').value;
  const variants = result.scenario[metric].without_one;
  result.sensitivity_selection = {
    metric, omitted_id: target.id === 'sensitivity-case' ? target.value : variants[0].omitted_id,
  };
  document.querySelector('#sensitivity-panel').outerHTML = sensitivityPanel(result);
  document.getElementById(target.id).focus();
}
