# CRM Maiharta – PRD / progress
Repo asli: github.com/gevinjanitto/crm-server (React CRA/craco + FastAPI + MySQL via docstore Mongo-like). Deploy: VPS Docker + Caddy (deploy/).

## Sesi 1 (diagnosa, tanpa ubah kode)
- Gmail `unauthorized_client`: refresh token dari OAuth client berbeda → dibuat ulang (user sudah beres).
- WA HTTP 500: device `portal-maiharta` belum login → sudah discan. WA 429 = WhatsApp error 463 reach-out timelock (penerima harus chat dulu; bot tidak resmi). Rekomendasi: WhatsApp Cloud API resmi.

## Sesi 2 (Okt 2026) – diimplementasikan
- Notifikasi web (Web Push/VAPID): backend/push.py (/api/push/public-key|status|subscribe|unsubscribe|test), dikirim untuk setiap notifikasi lonceng (notify.py). Subscription 404/410 dihapus otomatis.
- PWA: public/manifest.json, public/sw.js, ikon app-icon-*, registrasi SW di index.js, UI WebPushSettings (toggle per perangkat, tombol/petunjuk pasang aplikasi, uji notifikasi web).
- Peringatan "notifikasi gagal" ke admin dihapus (notification_delivery.py).
- MCP wajib OAuth (api_tokens.oauth_principal); PAT hanya untuk REST.
- setup.sh lokal (root), deploy/vapid.sh (generate VAPID, dipanggil setup/update), docker-compose + .env.example + Caddyfile (no-cache sw/manifest).
- Testing: iteration_33 – backend & frontend lulus.

## Backlog
- P1: WhatsApp Cloud API resmi (template satu baris).
- P2: Daftar perangkat notifikasi web per user + hapus perangkat.
- P2: Pengingat untuk mengaktifkan notifikasi web setelah login.

## Update Juni 2026
- Upload lampiran dari ChatGPT lewat link file (openai/fileParams: lampiran/file), base64 tetap jadi cadangan
- Notifikasi WhatsApp pindah ke Twilio (TWILIO_*), Sandbox dulu lalu nomor resmi + TWILIO_CONTENT_SID
- Panduan: DEPLOY_IDCLOUDHOST.md langkah 7, panduan-notifikasi.md bagian B
