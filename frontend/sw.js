/* আলোক service worker — cache the app shell so pages open instantly;
   detection requests always go to the network. */

const CACHE = 'alok-shell-v7';
const SHELL = [
  '/',
  '/index.html',
  '/live.html',
  '/read.html',
  '/help.html',
  '/css/app.css',
  '/js/common.js',
  '/js/i18n.js',
  '/js/live.js',
  '/js/read.js',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  // cache:'reload' bypasses the HTTP cache so a new SW never precaches
  // stale copies of updated files
  event.waitUntil(
    caches.open(CACHE).then((c) =>
      c.addAll(SHELL.map((u) => new Request(u, { cache: 'reload' })))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Detection API: network only — stale detections are worse than none
  if (url.pathname.startsWith('/detect')) return;

  // Shell: cache first, refresh in background
  if (event.request.method === 'GET' && url.origin === location.origin) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const fetched = fetch(event.request)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(event.request, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || fetched;
      })
    );
  }
});
