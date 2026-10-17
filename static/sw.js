/**
 * SERVICE WORKER FOR STATIC ASSET OPTIMIZATION
 * Dr. Dhvani Patalia Physio Rehab
 *
 * SAFETY INVARIANT:
 * - NEVER caches dynamic responses, patient records, auth tokens, or private endpoints.
 * - ONLY caches versioned static CSS, JS, and brand graphics to accelerate repeat page loads.
 */

const CACHE_NAME = 'physiorehab-static-v1';
const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/layout.js',
  '/static/js/preloader.js',
  '/static/images/favicon.ico',
  '/static/images/favicon-32x32.png',
  '/static/images/favicon-16x16.png',
  '/static/images/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        // Continue even if some individual assets fail to precache
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // STRICT BYPASS: Never intercept or cache non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // STRICT BYPASS: Never cache admin, client portals, APIs, auth, or media uploads
  if (
    url.pathname.startsWith('/admin') ||
    url.pathname.startsWith('/client') ||
    url.pathname.startsWith('/staff') ||
    url.pathname.startsWith('/super-admin') ||
    url.pathname.startsWith('/api') ||
    url.pathname.startsWith('/login') ||
    url.pathname.startsWith('/register') ||
    url.pathname.startsWith('/logout') ||
    url.pathname.startsWith('/media')
  ) {
    return; // Pass through directly to network
  }

  // For static assets: Stale-While-Revalidate or Cache-First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        if (cachedResponse) {
          // Return cached asset immediately, update cache in background
          fetch(event.request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, networkResponse));
              }
            })
            .catch(() => {});
          return cachedResponse;
        }
        return fetch(event.request);
      })
    );
  }
});
