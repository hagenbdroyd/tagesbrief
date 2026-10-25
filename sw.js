'use strict';
// =====================================================================
//  Tagesbrief – Service Worker (offline lesen, Push-Nachrichten)
// =====================================================================
// Immer zuerst aus dem Netz laden, damit die News aktuell sind.
// Nur ohne Verbindung wird die zuletzt gespeicherte Version gezeigt.

const CACHE = 'tagesbrief-v3';
const SHELL = ['./', 'index.html', 'styles.css', 'app.js', 'manifest.webmanifest', 'data/briefing.json', 'data/state.json', 'icons/icon.svg', 'icons/icon-192.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(url.pathname, copy));
        }
        return res;
      })
      .catch(() => caches.match(url.pathname, { ignoreSearch: true })
        .then((hit) => hit || (e.request.mode === 'navigate' ? caches.match('./') : Response.error()))),
  );
});

// ---------- Push: Morgen-Briefing und Eilmeldungen
self.addEventListener('push', (e) => {
  let data = {};
  try {
    data = e.data ? e.data.json() : {};
  } catch {
    data = { body: e.data?.text() };
  }
  // iOS verlangt, dass jeder Push sichtbar angezeigt wird
  e.waitUntil(self.registration.showNotification(data.title || 'Tagesbrief', {
    body: data.body || '',
    icon: 'icons/icon-192.png',
    tag: data.tag,
    data: { url: data.url || './' },
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = new URL(e.notification.data?.url || './', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
    const open = windows.find((w) => 'focus' in w);
    return open ? open.focus() : self.clients.openWindow(url);
  }));
});
