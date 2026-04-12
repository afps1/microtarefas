// Service Worker — network-only + Web Push — v2
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
      icon: "/app/icons/icon-192.png",
      badge: "/app/icons/badge-72.png",
      vibrate: [200, 100, 200],
      tag: "nova-tarefa",
      renotify: true,
    }).then(() => {
      if (navigator.setAppBadge) navigator.setAppBadge();
      // Avisa o app aberto para atualizar a lista imediatamente
      return self.clients.matchAll({ type: "window" }).then(clients => {
        clients.forEach(c => c.postMessage({ type: "NEW_TASK" }));
      });
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
