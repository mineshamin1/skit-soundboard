// Service worker: pre-caches the app and every sound so the show runs with no network.
// Bump CACHE whenever cues.json or the sounds change, so phones pick up the new files.
const CACHE = 'skit-soundboard-v9';
const CORE = ['./', 'index.html', 'cues.json', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'sounds/_silence.mp3'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const res = await fetch('cues.json', { cache: 'no-cache' });
    const data = await res.json();
    const files = CORE.concat(data.sounds.map((s) => s.file));
    await cache.addAll(files);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
    const clients = await self.clients.matchAll({ includeUncontrolled: true });
    clients.forEach((c) => c.postMessage({ type: 'cached' }));
  })());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith((async () => {
    const cached = await caches.match(event.request, { ignoreSearch: true });
    if (cached) return cached;
    try {
      const res = await fetch(event.request);
      if (res.ok && new URL(event.request.url).origin === self.location.origin) {
        const cache = await caches.open(CACHE);
        cache.put(event.request, res.clone());
      }
      return res;
    } catch (e) {
      return new Response('Offline and not cached', { status: 503 });
    }
  })());
});
