// Service Worker — network-only + Web Push
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  e.respondWith(fetch(e.request));
});

self.addEventListener("push", (e) => {
  let data = { title: "Nova tarefa!", body: "Abra o app para ver." };
  try { data = e.data?.json() || data; } catch {}
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/app/icons/icon-192.svg",
      badge: "/app/icons/icon-192.svg",
      vibrate: [200, 100, 200],
      tag: "nova-tarefa",
      renotify: true,
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes("/app/") && "focus" in c) return c.focus();
      }
      return clients.openWindow("/app/dashboard.html");
    })
  );
});
