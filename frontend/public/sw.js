/* Service worker CRM Maiharta: notifikasi web (push) dan klik notifikasi. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(data.title || 'CRM Maiharta', {
    body: data.body || '',
    icon: '/assets/app-icon-192.png',
    badge: '/assets/app-badge-96.png',
    tag: data.id || undefined,
    data: { url: data.url || '/notifications' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/notifications', self.location.origin).href;
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    const open = list.find((c) => c.url.startsWith(self.location.origin));
    if (open) { open.focus(); return open.navigate ? open.navigate(target) : null; }
    return self.clients.openWindow(target);
  }));
});
