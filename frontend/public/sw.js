const CACHE_NAME = "medical-passport-static-shell-v1";
const STATIC_SHELL = [
  "/offline-card.html",
  "/offline-card.css",
  "/offline-card-crypto.js",
  "/offline-card.js",
  "/manifest.webmanifest",
  "/icons/medical-passport.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_SHELL)),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(async (keys) => {
      await Promise.all(
        keys
          .filter((key) => key.startsWith("medical-passport-static-shell-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    }),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !STATIC_SHELL.includes(url.pathname)) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(url.pathname);
      if (cached) return cached;

      const response = await fetch(request);
      if (response.ok && response.type === "basic") {
        await cache.put(url.pathname, response.clone());
      }
      return response;
    }),
  );
});
