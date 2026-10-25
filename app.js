'use strict';
// =====================================================================
//  Tagesbrief – Anzeige des täglichen Briefings
// =====================================================================

const DATA_URL = 'data/briefing.json';
const TZ = 'Europe/Berlin';
const WORDS_PER_MINUTE = 200;

const app = document.getElementById('app');
const progressBar = document.getElementById('progress');
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const CHECK_ICON = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

let current = null; // zuletzt angezeigtes Briefing

// ---------- Datum & Zeit (immer deutsche Zeit, auch im Urlaub)
const dayKey = (iso) => new Date(iso).toLocaleDateString('en-CA', { timeZone: TZ });
const formatTime = (iso) => new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: TZ }).format(new Date(iso));
const formatDate = (day) => new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ }).format(new Date(`${day}T12:00:00Z`));

function timeLabel(iso, briefingDay) {
  if (dayKey(iso) === briefingDay) return `${formatTime(iso)} Uhr`;
  const yesterday = new Date(`${briefingDay}T12:00:00Z`);
  yesterday.setUTCDate(yesterday.getUTCDate() - 1);
  const prefix = dayKey(iso) === dayKey(yesterday.toISOString()) ? 'gestern' : formatDate(dayKey(iso));
  return `${prefix}, ${formatTime(iso)} Uhr`;
}

function readingMinutes(items) {
  const words = items.map((i) => `${i.headline} ${i.summary}`).join(' ').split(/\s+/).length;
  return Math.max(1, Math.round(words / WORDS_PER_MINUTE));
}

// =====================================================================
//  Bausteine der Seite
// =====================================================================
function renderSources(sources, label) {
  return `
    <div class="sources">
      <span class="sources-label">${label}</span>
      ${sources.map((s) => `<a class="source" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}${s.country ? `<span class="cc">${esc(s.country)}</span>` : ''}</a>`).join('')}
    </div>`;
}

function renderBreaking(b) {
  return `
    <section class="breaking">
      <div class="breaking-label">Eilmeldung · ${formatTime(b.time)} Uhr</div>
      <h2>${esc(b.headline)}</h2>
      <p>${esc(b.summary)}</p>
      ${renderSources(b.sources, 'Bestätigt von:')}
    </section>`;
}

function renderItem(item, num) {
  return `
    <article class="item">
      <div class="num">${num}</div>
      <div>
        <h3>${esc(item.headline)}</h3>
        <p class="summary">${esc(item.summary)}</p>
        ${renderSources(item.sources, 'Quellen:')}
        ${item.perspectives ? `
          <details class="perspective">
            <summary>Wie berichten die Medien?</summary>
            <p>${esc(item.perspectives)}</p>
          </details>` : ''}
      </div>
    </article>`;
}

function renderSection(section, startNum) {
  return `
    <section class="section" data-id="${esc(section.id)}">
      <div class="section-head"><h2>${esc(section.title)}</h2></div>
      ${section.items.map((item, i) => renderItem(item, startNum + i)).join('')}
    </section>`;
}

function renderHeadlines(briefing, filter) {
  const list = briefing.more.filter((h) => filter === 'alle' || h.section === filter);
  $('#headlines').innerHTML = list.length
    ? list.map((h) => `
        <li>
          <a href="${esc(h.url)}" target="_blank" rel="noopener">
            <span class="hl-title">${esc(h.headline)}</span>
            <span class="hl-meta">${h.opinion ? '<span class="hl-tag">Meinung</span> ' : ''}${esc(h.source)}${h.country ? ` (${esc(h.country)})` : ''} · ${timeLabel(h.time, briefing.date)}</span>
          </a>
        </li>`).join('')
    : '<li class="hl-meta">Keine weiteren Schlagzeilen.</li>';
}

// =====================================================================
//  Ganze Seite
// =====================================================================
// "gemini-3.8-flash" → "Gemini 3.8 Flash"
const modelName = (id) => id.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');

function render(briefing) {
  const breaking = briefing.breaking || [];
  const items = [...breaking, ...briefing.sections.flatMap((s) => s.items)];
  const headlinesOnly = items.length === 0; // KI ist ausgefallen → gleich die Schlagzeilen zeigen
  let num = 1;
  const sections = briefing.sections.filter((s) => s.items.length).map((s) => {
    const html = renderSection(s, num);
    num += s.items.length;
    return html;
  });
  const tabs = [{ id: 'alle', title: 'Alle' }, ...briefing.sections];
  const meta = headlinesOnly
    ? `Heute nur Schlagzeilen · Stand ${formatTime(briefing.generatedAt)} Uhr`
    : `${items.length} Punkte · ca. ${readingMinutes(items)} Min. · Stand ${formatTime(briefing.generatedAt)} Uhr`;

  app.innerHTML = `
    <header>
      <div class="brand">Tagesbrief</div>
      <h1 class="date">${formatDate(briefing.date).replace(', ', ',<br>')}</h1>
      <p class="meta">${meta}</p>
    </header>
    ${briefing.notice ? `<p class="sample-note">${esc(briefing.notice)}</p>` : ''}
    ${breaking.map(renderBreaking).join('')}
    ${sections.join('')}

    ${headlinesOnly ? '' : `
    <section class="done" id="done">
      <div class="done-check">${CHECK_ICON}</div>
      <h2>Du bist durch für heute.</h2>
      <p>Das nächste Briefing kommt morgen gegen 7 Uhr.</p>
      <button class="btn" id="more-btn" type="button">Mehr Schlagzeilen</button>
    </section>`}

    <section class="more" id="more" ${headlinesOnly ? '' : 'hidden'}>
      <h2>${headlinesOnly ? 'Schlagzeilen' : 'Weitere Schlagzeilen'}</h2>
      <p class="more-hint">${briefing.aiModel ? 'Von der KI ausgewählt, Schlagzeilen im Original aus den Quellen.' : 'Die neuesten Schlagzeilen, im Original aus den Quellen.'}</p>
      <div class="tabs" role="tablist">
        ${tabs.map((t, i) => `<button class="tab" role="tab" type="button" data-filter="${esc(t.id)}" aria-selected="${i === 0}">${esc(t.title)}</button>`).join('')}
      </div>
      <ul class="headlines" id="headlines"></ul>
    </section>

    ${briefing.aiModel ? `<p class="disclaimer">Zusammenfassungen von KI erstellt (${esc(modelName(briefing.aiModel))}) – Fehler sind möglich. Prüf im Zweifel die verlinkte Originalquelle.</p>` : ''}`;

  renderHeadlines(briefing, 'alle');

  $('#more-btn')?.addEventListener('click', (e) => {
    e.currentTarget.hidden = true;
    $('#more').hidden = false;
    $('#more').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  $('#more .tabs').addEventListener('click', (e) => {
    const tab = e.target.closest('.tab');
    if (!tab) return;
    for (const t of e.currentTarget.children) t.setAttribute('aria-selected', String(t === tab));
    renderHeadlines(briefing, tab.dataset.filter);
  });

  updateProgress();
}

// ---------- Lesefortschritt: voll, sobald „Du bist durch“ ganz sichtbar ist
function updateProgress() {
  const done = $('#done');
  if (!done) return;
  const end = done.offsetTop + done.offsetHeight - window.innerHeight;
  const ratio = end > 0 ? Math.min(1, Math.max(0, window.scrollY / end)) : 1;
  progressBar.style.transform = `scaleX(${ratio})`;
}

let progressFrame = 0;
const scheduleProgress = () => {
  cancelAnimationFrame(progressFrame);
  progressFrame = requestAnimationFrame(updateProgress);
};
window.addEventListener('scroll', scheduleProgress, { passive: true });
window.addEventListener('resize', scheduleProgress);

// =====================================================================
//  Laden
// =====================================================================
async function load() {
  try {
    const res = await fetch(DATA_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const briefing = await res.json();
    if (current && current.generatedAt === briefing.generatedAt) return;
    current = briefing;
    render(briefing);
  } catch (err) {
    console.error('Briefing konnte nicht geladen werden', err);
    if (current) return; // altes Briefing lieber stehen lassen als Fehler zeigen
    app.innerHTML = `
      <p class="status">
        Briefing konnte nicht geladen werden.<br>
        <button class="btn" id="retry" type="button">Nochmal versuchen</button>
      </p>`;
    $('#retry').addEventListener('click', load);
  }
}

// Als Homescreen-App bleibt die Seite oft tagelang offen → beim Zurückkehren neu laden
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') load();
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}

load();
