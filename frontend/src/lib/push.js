import { api } from './api';

const toBytes = (b64) => {
  const raw = atob((b64 + '='.repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};

export const pushSupported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
export const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
export const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

const registration = async () => (await navigator.serviceWorker.getRegistration('/')) || navigator.serviceWorker.register('/sw.js');

export async function currentSubscription() {
  if (!pushSupported()) return null;
  return (await registration()).pushManager.getSubscription();
}

// Daftarkan ulang langganan lokal ke server (mis. setelah dihapus server) agar toggle selalu sesuai.
export async function syncSubscription() {
  const sub = await currentSubscription();
  if (!sub || Notification.permission !== 'granted') return false;
  const json = sub.toJSON();
  await api.post('/push/subscribe', { endpoint: json.endpoint, keys: json.keys, device: deviceName() });
  return true;
}

const deviceName = () => {
  const ua = navigator.userAgent;
  const os = /android/i.test(ua) ? 'Android' : isIOS() ? 'iOS' : /windows/i.test(ua) ? 'Windows' : /mac/i.test(ua) ? 'macOS' : 'Linux';
  const browser = /edg\//i.test(ua) ? 'Edge' : /firefox/i.test(ua) ? 'Firefox' : /chrome|crios/i.test(ua) ? 'Chrome' : /safari/i.test(ua) ? 'Safari' : 'Browser';
  return `${browser} · ${os}`;
};

export async function enablePush() {
  if (Notification.permission === 'denied') throw new Error('Notifikasi diblokir di pengaturan browser/perangkat. Izinkan dulu, lalu coba lagi.');
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Izin notifikasi tidak diberikan.');
  const { data } = await api.get('/push/public-key');
  const reg = await registration();
  const sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toBytes(data.public_key) });
  const json = sub.toJSON();
  await api.post('/push/subscribe', { endpoint: json.endpoint, keys: json.keys, device: deviceName() });
}

export async function disablePush() {
  const sub = await currentSubscription();
  if (!sub) return;
  await api.post('/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {});
  await sub.unsubscribe();
}
