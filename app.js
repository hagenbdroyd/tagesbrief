'use strict';
// =====================================================================
//  Tagesbrief – Anzeige des täglichen Briefings
// =====================================================================

const DATA_URL = 'data/briefing.json';
const STATE_URL = 'data/state.json'; // Eilmeldungen vom Wächter (läuft alle 15 Minuten)
const TZ = 'Europe/Berlin';
const WORDS_PER_MINUTE = 200;
const BREAKING_HOURS = 24; // so lange bleibt eine Eilmeldung oben stehen
// Öffentlicher Push-Schlüssel – der private liegt verschlüsselt bei GitHub
const VAPID_PUBLIC_KEY = 'BHrzkLFjPGHhYTCJ1DzXY_ZM5eqbVonsdfhnpOduNOaqp2vWgQ1hcpj-WgKrdcTmbaPBcCtlRisCD8gQde3B510';

const app = document.getElementById('app');
const progressBar = document.getElementById('progress');
const topbarDate = document.getElementById('topbar-date');
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const CHECK_ICON = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

let shownVersion = null; // Stand des zuletzt angezeigten Briefings (Briefing + Eilmeldungen)

// ---------- Datum & Zeit (immer deutsche Zeit, auch im Urlaub)
const dayKey = (iso) => new Date(iso).toLocaleDateString('en-CA', { timeZone: TZ });
const formatTime = (iso) => new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: TZ }).format(new Date(iso));
const formatDate = (day) => new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: 'numeric', month: 'long', timeZone: TZ }).format(new Date(`${day}T12:00:00Z`));
const formatDateShort = (day) => new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: 'numeric', month: 'short', timeZone: TZ }).format(new Date(`${day}T12:00:00Z`));

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

// Fotos kommen direkt von den Medien; lädt eins nicht, verschwindet der Platz dafür (siehe unten)
function renderImage(image, eager = false) {
  if (!image?.url) return '';
  return `
    <figure class="card-img">
      <img src="${esc(image.url)}" alt="" ${eager ? '' : 'loading="lazy"'} decoding="async" referrerpolicy="no-referrer">
      <figcaption>Foto: ${esc(image.source)}</figcaption>
    </figure>`;
}

function renderBreaking(b) {
  return `
    <article class="card breaking">
      ${renderImage(b.image, true)}
      <div class="card-body">
        <div class="breaking-label">Eilmeldung · ${timeLabel(b.time, dayKey(new Date().toISOString()))}</div>
        <h2>${esc(b.headline)}</h2>
        <p class="summary">${esc(b.summary)}</p>
        ${renderSources(b.sources, 'Bestätigt von')}
      </div>
    </article>`;
}

function renderItem(item, num) {
  return `
    <article class="card story">
      ${renderImage(item.image, num === 1)}
      <div class="card-body">
        <div class="kicker"><span class="num">${num}</span></div>
        <h3>${esc(item.headline)}</h3>
        <p class="summary">${esc(item.summary)}</p>
        ${item.perspectives ? `
          <details class="perspective">
            <summary>Wie berichten die Medien?</summary>
            <p>${esc(item.perspectives)}</p>
          </details>` : ''}
        ${renderSources(item.sources, 'Quellen')}
      </div>
    </article>`;
}

function renderSection(section, startNum) {
  return `
    <section class="section" data-id="${esc(section.id)}">
      <h2 class="section-title">${esc(section.title)}</h2>
      ${section.items.map((item, i) => renderItem(item, startNum + i)).join('')}
    </section>`;
}

function renderHeadlines(briefing, filter) {
  const list = briefing.more.filter((h) => filter === 'alle' || h.section === filter);
  $('#headlines').innerHTML = list.length
    ? list.map((h) => `
        <li>
          <a href="${esc(h.url)}" target="_blank" rel="noopener">
            <span class="hl-text">
              <span class="hl-title">${esc(h.headline)}</span>
              <span class="hl-meta">${h.opinion ? '<span class="hl-tag">Meinung</span> ' : ''}${esc(h.source)}${h.country ? ` · ${esc(h.country)}` : ''} · ${timeLabel(h.time, briefing.date)}</span>
            </span>
            ${h.image ? `<img class="hl-thumb" src="${esc(h.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}
          </a>
        </li>`).join('')
    : '<li class="hl-empty">Keine weiteren Schlagzeilen.</li>';
}

// =====================================================================
//  Ganze Seite
// =====================================================================
// "gemini-3.8-flash" → "Gemini 3.8 Flash"
const modelName = (id) => id.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');

function render(briefing, state) {
  const since = Date.now() - BREAKING_HOURS * 3600e3;
  // Eilmeldungen, die ein neueres Briefing schon als normale Geschichte enthält, nicht doppelt zeigen
  const covered = new Set(briefing.sections.flatMap((s) => s.items).flatMap((i) => i.sources.map((src) => src.url)));
  const inBriefing = (b) => new Date(b.pushedAt) <= new Date(briefing.generatedAt) && b.sources.some((src) => covered.has(src.url));
  const watched = (state?.breaking || []).filter((b) => new Date(b.time) >= since && !inBriefing(b)).reverse(); // neueste zuerst
  const breaking = [...watched, ...(briefing.breaking || [])];
  const items = [...breaking, ...briefing.sections.flatMap((s) => s.items)];
  const headlinesOnly = items.length === 0; // KI ist ausgefallen → gleich die Schlagzeilen zeigen
  let num = 1;
  const sections = briefing.sections.filter((s) => s.items.length).map((s) => {
    const html = renderSection(s, num);
    num += s.items.length;
    return html;
  });
  const tabs = [{ id: 'alle', title: 'Alle' }, ...briefing.sections];
  // „Stand gestern, 09:56 Uhr“ statt nur „09:56 Uhr“, damit ein altes Briefing nicht wie ein aktuelles aussieht
  const stand = `Stand ${timeLabel(briefing.generatedAt, dayKey(new Date().toISOString()))}`;
  const meta = headlinesOnly
    ? `<span>Heute nur Schlagzeilen</span><span>${stand}</span>`
    : `<span>${items.length} Themen</span><span>ca. ${readingMinutes(items)} Min.</span><span>${stand}</span>`;

  topbarDate.textContent = formatDateShort(briefing.date);
  app.innerHTML = `
    <p class="meta">${meta}</p>
    ${briefing.notice ? `<p class="notice">${esc(briefing.notice)}</p>` : ''}
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

    <section class="push-card" id="push" hidden></section>

    ${briefing.aiModel ? `<p class="disclaimer">Zusammenfassungen von KI erstellt (${esc(modelName(briefing.aiModel))}) – Fehler sind möglich. Prüf im Zweifel die verlinkte Originalquelle.</p>` : ''}`;

  renderHeadlines(briefing, 'alle');
  renderPush();

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
//  Push-Benachrichtigungen
// =====================================================================
// Ablauf: Erlaubnis holen → beim Push-Dienst des iPhones anmelden → Verbindungs-Code anzeigen.
// Den Code hinterlegt Claude bei GitHub; von dort kommen Morgen-Push und Eilmeldungen.
const pushSupported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
const isHomescreenApp = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;

function base64UrlToBytes(text) {
  const base64 = (text + '='.repeat((4 - (text.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
}

const connectionCode = (sub) => `TB1.${btoa(JSON.stringify(sub.toJSON())).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}`;

async function currentSubscription() {
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

async function subscribe() {
  const reg = await navigator.serviceWorker.ready;
  const options = { userVisibleOnly: true, applicationServerKey: base64UrlToBytes(VAPID_PUBLIC_KEY) };
  try {
    return await reg.pushManager.subscribe(options);
  } catch (err) {
    // altes Abo mit anderem Schlüssel → abmelden und neu anmelden
    await (await reg.pushManager.getSubscription())?.unsubscribe();
    return reg.pushManager.subscribe(options);
  }
}

async function renderPush(showCode = false) {
  const box = $('#push');
  if (!box) return;
  box.hidden = false;

  if (!pushSupported() || !isHomescreenApp()) {
    box.innerHTML = `
      <h2>Benachrichtigungen</h2>
      <p>Morgen-Push und Eilmeldungen gibt es nur, wenn du den Tagesbrief über das Icon auf deinem Homescreen öffnest
      (Safari → Teilen → „Zum Home-Bildschirm“).</p>`;
    return;
  }
  if (Notification.permission === 'denied') {
    box.innerHTML = `
      <h2>Benachrichtigungen</h2>
      <p>Du hast Benachrichtigungen abgelehnt. Du kannst sie in den iPhone-Einstellungen unter
      „Mitteilungen → Tagesbrief“ wieder erlauben.</p>`;
    return;
  }

  const sub = Notification.permission === 'granted' ? await currentSubscription() : null;
  if (!sub) {
    box.innerHTML = `
      <h2>Benachrichtigungen</h2>
      <p>Jeden Morgen gegen 7 Uhr die wichtigste Schlagzeile, dazu Eilmeldungen nach deinen Regeln.</p>
      <button class="btn btn-primary" id="push-on" type="button">Benachrichtigungen aktivieren</button>`;
    $('#push-on').addEventListener('click', async (e) => {
      e.currentTarget.disabled = true;
      // muss direkt im Tipp passieren, sonst blockiert iOS die Abfrage
      const permission = await Notification.requestPermission();
      if (permission === 'granted') await subscribe();
      renderPush(true);
    });
    return;
  }

  const code = connectionCode(sub);
  box.innerHTML = `
    <h2>Benachrichtigungen sind an ${CHECK_ICON}</h2>
    ${showCode ? `
      <p>Letzter Schritt: Kopier diesen Verbindungs-Code und schick ihn Claude im Chat. Danach kommen die Pushs auf dieses iPhone.</p>
      <textarea class="push-code" readonly rows="4">${esc(code)}</textarea>
      <button class="btn btn-primary" id="push-copy" type="button">Code kopieren</button>` : `
      <button class="btn" id="push-show" type="button">Verbindungs-Code anzeigen</button>`}`;
  $('#push-show')?.addEventListener('click', () => renderPush(true));
  $('#push-copy')?.addEventListener('click', async (e) => {
    const button = e.currentTarget;
    try {
      await navigator.clipboard.writeText(code);
      button.textContent = 'Kopiert ✓';
    } catch {
      $('.push-code').select(); // Notlösung: markieren, dann selbst kopieren
      button.textContent = 'Markiert – jetzt kopieren';
    }
  });
}

// =====================================================================
//  Laden
// =====================================================================
async function fetchJson(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

async function load() {
  try {
    const [briefing, state] = await Promise.all([fetchJson(DATA_URL), fetchJson(STATE_URL).catch(() => null)]);
    const version = `${briefing.generatedAt}|${state?.updatedAt}`;
    if (version === shownVersion) return;
    shownVersion = version;
    render(briefing, state);
  } catch (err) {
    console.error('Briefing konnte nicht geladen werden', err);
    if (shownVersion) return; // altes Briefing lieber stehen lassen als Fehler zeigen
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

// Foto lädt nicht (gelöscht, gesperrt)? Dann den Platz dafür entfernen statt ein kaputtes Bild zu zeigen
document.addEventListener('error', (e) => {
  if (e.target.tagName !== 'IMG') return;
  (e.target.closest('.card-img') || e.target).remove();
}, true);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}

load();
