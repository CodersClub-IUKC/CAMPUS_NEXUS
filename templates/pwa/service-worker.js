const CACHE_PREFIX = "campus-nexus-pwa-";
const CACHE_VERSION = "{{ cache_version|escapejs }}";
const STATIC_CACHE = `${CACHE_PREFIX}${CACHE_VERSION}`;
const OFFLINE_URL = "/offline/";
const STATIC_URL = "{{ static_url|escapejs }}";

const PRECACHE_URLS = [
  OFFLINE_URL,
  `${STATIC_URL}img/CAMPUS_NEXUS.png`,
  `${STATIC_URL}img/favicon.ico`,
  `${STATIC_URL}img/pwa-icon-192.png`,
  `${STATIC_URL}img/pwa-icon-512.png`,
];

const SENSITIVE_PREFIXES = [
  "/admin/login/",
  "/admin/logout/",
  "/admin/password_reset/",
  "/reset/",
  "/api/",
  "/api/v2/campus_nexus/",
];

function isSameOrigin(url) {
  return url.origin === self.location.origin;
}

function isSensitivePath(pathname) {
  return SENSITIVE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(STATIC_CACHE);
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith(CACHE_PREFIX) && key !== STATIC_CACHE)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (!isSameOrigin(url) || request.method !== "GET" || isSensitivePath(url.pathname)) {
    return;
  }

  if (
    url.pathname.startsWith(STATIC_URL) ||
    url.pathname === "/favicon.ico" ||
    url.pathname === "/manifest.webmanifest"
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
  }
});
