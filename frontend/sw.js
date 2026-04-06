// Service Worker — network-only (sem cache)
// Qualquer atualização no servidor aparece imediatamente.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  e.respondWith(fetch(e.request));
});
