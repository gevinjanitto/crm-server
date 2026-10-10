# Panduan notifikasi CRM Maiharta

Alur notifikasi: **Backend CRM (Railway) → n8n (Railway) → Gmail / WAHA**.

- Email: n8n mengirim lewat **Gmail API** (HTTPS), aman untuk Railway Hobby yang memblokir SMTP.
- WhatsApp: n8n meneruskan ke **WAHA** (WhatsApp HTTP API) yang Anda pasang sendiri di Railway.
- Satu secret yang sama (`N8N_WAHA_WEBHOOK_SECRET`) dipakai backend untuk kedua webhook n8n.

---

## 1. Cek cepat: kenapa email belum masuk?

Periksa berurutan. Hampir semua kasus berhenti di salah satu poin ini.

| No | Cek | Yang benar |
| --- | --- | --- |
| 1 | URL webhook di Railway | `N8N_EMAIL_WEBHOOK_URL=https://<domain-n8n>/webhook/crm-email`. **Bukan** `/webhook-test/...` (URL test hanya hidup sekali saat Anda klik *Execute workflow*; backend menolaknya). |
| 2 | Workflow email di n8n | Status **Active / Published** (toggle kanan atas). |
| 3 | Secret | Nilai `N8N_WAHA_WEBHOOK_SECRET` di Railway **sama persis** dengan credential Header Auth `CRM Webhook Secret` (`X-CRM-Webhook-Secret`) di n8n. Minimal 32 karakter. |
| 4 | Variables backend lengkap | `EMAIL_ENABLED=true`, `N8N_EMAIL_WEBHOOK_URL`, `N8N_WAHA_WEBHOOK_SECRET`, `APP_URL` (HTTPS frontend). |
| 5 | Kode terbaru sudah deploy | Railway → service backend → **Deployments**: commit paling baru berstatus *Success*. Setelah *Save to GitHub*, tunggu deploy otomatis selesai. |
| 6 | Akun penerima | Pengaturan → Notifikasi akun → toggle **Email** menyala lalu **Simpan**. Email akun harus asli (alamat `@*.example` tidak dikirim). |
| 7 | Bukan aksi sendiri | Orang yang **melakukan** aksi tidak menerima notifikasi atas aksinya sendiri. Contoh: Admin membuat maintenance → yang menerima Admin Project lain, bukan Admin itu sendiri. Untuk tes, pakai tombol **Uji** atau lakukan aksi dari akun lain. |

Setelah itu buka **Pengaturan → Notifikasi akun**:

- Kotak *Gmail via n8n* harus bertuliskan **Konfigurasi tersedia**. Jika *Belum aktif*, catatan di bawahnya menyebut variabel yang salah.
- Klik **Uji**. Bagian **Pengiriman terakhir** menampilkan hasil dan alasan, misalnya:
  - `HTTP 403` → secret di Railway berbeda dengan n8n.
  - `HTTP 404` → workflow belum Active atau URL salah.
  - `HTTP 502` → n8n gagal ke Gmail (login Gmail di n8n kedaluwarsa, ulangi *Sign in with Google*).
- Buka n8n → **Executions** untuk melihat detail tiap pengiriman.

### Email masuk folder Spam?

**Langkah 1 — pakai workflow email versi 2 (disarankan).** Versi 2 mengirim lewat Gmail API dengan email *multipart* (teks + HTML), nama pengirim `CRM Maiharta`, header `List-Unsubscribe`, dan desain email bermerek. Ini jauh lebih disukai filter spam dibanding email HTML saja.

1. n8n → buka workflow email lama → matikan toggle **Active** (atau hapus workflow lama). Path `crm-email` tidak boleh dipakai dua workflow.
2. Unduh **Workflow Email** (Pengaturan → Notifikasi akun, atau tombol di atas) → **Import from File**.
3. Node **Webhook CRM** → credential `CRM Webhook Secret`.
4. Node **Profil Gmail** dan **Kirim via Gmail API** → *Credential for Gmail OAuth2 API* → pilih credential Gmail yang sudah ada.
5. **Publish / Activate**, lalu CRM → Pengaturan → **Uji notifikasi**.

**Langkah 2 — ajari Gmail penerima** (sekali saja):

1. Di Gmail penerima, buka email di **Spam** → klik **Laporkan bukan spam**.
2. Buka email → klik nama pengirim → **Tambahkan ke kontak**.
3. (Disarankan) Gmail → kotak cari → ikon filter → **Dari** = alamat Gmail pengirim n8n → **Buat filter** → centang **Jangan pernah kirim ke Spam** (+ opsional *Tandai sebagai penting*) → Buat filter.
4. Minta setiap penerima melakukan langkah 1–2 sekali.
5. Jangan kirim email uji berulang-ulang dalam waktu singkat; volume tinggi dengan isi mirip memicu filter spam.

---

## 2. Email via n8n + Gmail

### 2.1 Credential secret webhook (sekali saja)

1. Buat secret acak 40+ karakter: terminal `openssl rand -hex 32`, atau https://www.random.org/strings/ (huruf + angka).
2. n8n → **Credentials → Add credential → Header Auth**:
   - Nama credential: `CRM Webhook Secret`
   - Name: `X-CRM-Webhook-Secret`
   - Value: secret tadi
3. Credential yang sama dipakai workflow Email **dan** WhatsApp.

### 2.2 Impor workflow email

1. Unduh **Workflow Email Gmail** (tombol di atas halaman ini) → n8n **Workflows → Import from File**.
2. Node **Webhook CRM** → Authentication *Header Auth* → pilih `CRM Webhook Secret`.
3. Node **Kirim via Gmail** → credential **Gmail OAuth2** → *Sign in with Google* (lihat 2.3 untuk Client ID).
4. Klik **Publish / Activate**. Salin **Production URL** node Webhook: `https://<domain-n8n>/webhook/crm-email`.

### 2.3 Gmail OAuth2 untuk n8n self-host

1. https://console.cloud.google.com → buat project `crm-maiharta-n8n`.
2. **APIs & Services → Library** → aktifkan **Gmail API**.
3. **OAuth consent screen** → External → isi nama & email → tambah email Gmail Anda di **Test users** → **Publish app** (agar login tidak kedaluwarsa tiap 7 hari).
4. **Credentials → Create credentials → OAuth client ID** → *Web application* → **Authorized redirect URIs** = *OAuth Redirect URL* dari dialog credential Gmail di n8n (`https://<domain-n8n>/rest/oauth2-credential/callback`).
5. Salin **Client ID** dan **Client Secret** ke credential Gmail di n8n → **Sign in with Google** → izinkan.

> Jangan *Generate Domain* baru untuk n8n. Jika domain n8n berubah, URL webhook di Railway dan redirect URI di Google wajib diganti juga.

### 2.4 Variables backend CRM di Railway

Railway → service **backend CRM** → **Variables → Raw Editor**, tambahkan/ubah:

```text
EMAIL_ENABLED=true
N8N_EMAIL_WEBHOOK_URL=https://<domain-n8n>/webhook/crm-email
N8N_WAHA_WEBHOOK_SECRET=<secret dari 2.1>
MAIL_SENDER_NAME=CRM Maiharta
APP_URL=https://crm-maiharta.vercel.app
```

Hapus variabel lama yang tidak dipakai lagi: `EMAIL_PROVIDER`, `RESEND_API_KEY`, `RESEND_API_URL`, `MAIL_FROM`, `EMAIL_REPLY_TO`. Klik **Deploy** setelah menyimpan.

---

## 3. WhatsApp: pasang WAHA di Railway

WAHA adalah server WhatsApp yang ditautkan ke nomor WhatsApp Anda (seperti WhatsApp Web). Gunakan nomor khusus bisnis, karena WAHA bukan API resmi Meta dan nomor bisa dibatasi jika dipakai spam.

### 3.1 Buat service WAHA

1. Buka project Railway yang sama dengan n8n → **+ Create → Docker Image**.
2. Ketik `devlikeapro/waha:latest` lalu tekan tombol **Enter** di keyboard. **Jangan klik** tautan ungu `hub.docker.com/r/devlikeapro/waha` yang muncul di bawahnya: itu hanya link ke halaman Docker Hub dan membuka tab baru. Setelah Enter, kartu service baru muncul di canvas → klik **Deploy** (atau tombol *Deploy* di kanan atas). Ganti nama service menjadi `waha` (Settings → Service Name).
3. Tambah volume: di canvas project, **klik kanan kartu service `waha` → Attach Volume** (atau tekan `Ctrl+K` / `⌘K` → ketik *volume* → pilih **Add Volume** → pilih service `waha`). Isi Mount path: `/app/.sessions` → Create. Klik **Deploy** bila muncul tombol perubahan. (Tanpa volume, Anda harus scan QR ulang setiap restart.)
4. Settings → **Replicas = 1**, dan pastikan *Serverless / App Sleeping* **mati**.

### 3.2 Variables service WAHA

Buat 2 secret baru (masing-masing `openssl rand -hex 32`): satu untuk API key, satu untuk password dashboard. **Jangan** sama dengan secret webhook CRM.

Service `waha` → **Variables → Raw Editor**:

```text
PORT=3000
WHATSAPP_API_PORT=3000
WHATSAPP_DEFAULT_ENGINE=WEBJS
WAHA_API_KEY=<secret API key WAHA>
WAHA_DASHBOARD_ENABLED=true
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=<password dashboard>
WHATSAPP_SWAGGER_ENABLED=false
WAHA_PRINT_QR=false
TZ=Asia/Makassar
```

> RAM terbatas? Pakai image `devlikeapro/waha:noweb` dan `WHATSAPP_DEFAULT_ENGINE=NOWEB` (lebih ringan, tanpa browser).

### 3.3 Domain & scan QR

1. Service `waha` → **Settings → Networking → Generate Domain** → Target port `3000`. Dapat URL seperti `https://waha-production-xxxx.up.railway.app`.
2. Buka `https://<domain-waha>/dashboard` → login `admin` + password dashboard.
3. Saat diminta, isi **API Key** = nilai `WAHA_API_KEY`.
4. Session `default` → **Start** → klik ikon QR.
5. Di HP: **WhatsApp → Perangkat tertaut → Tautkan perangkat** → scan QR.
6. Tunggu status **WORKING**.

### 3.4 Impor workflow WhatsApp di n8n

1. Unduh **Workflow WhatsApp** (tombol di atas) → n8n **Import from File**.
2. Node **Webhook CRM** → Header Auth → pilih `CRM Webhook Secret` (sama dengan email).
3. Node **Konfigurasi WAHA** → `waha_base_url` = `https://<domain-waha>` (tanpa `/` di akhir). `waha_session` = `default`.
4. Buat credential **Header Auth** baru bernama `WAHA API Key`: Name `X-Api-Key`, Value = nilai `WAHA_API_KEY`.
5. Node **Kirim via WAHA** → Authentication *Generic Credential Type → Header Auth* → pilih `WAHA API Key`. Biarkan *Retry On Fail* mati.
6. **Publish / Activate**. Production URL: `https://<domain-n8n>/webhook/crm-whatsapp`.

### 3.5 Variables backend CRM di Railway (WhatsApp)

Tambahkan ke service **backend CRM**, lalu Deploy:

```text
WHATSAPP_ENABLED=true
N8N_WAHA_WEBHOOK_URL=https://<domain-n8n>/webhook/crm-whatsapp
```

`N8N_WAHA_WEBHOOK_SECRET` dan `APP_URL` sudah diisi di langkah email. WAHA API key **tidak** perlu dimasukkan ke backend CRM.

### 3.6 Aktifkan di akun

1. CRM → **Pengaturan → Notifikasi akun** → nyalakan **WhatsApp** → isi nomor (`0812...` otomatis jadi `+62812...`) → **Simpan notifikasi**.
2. Klik **Uji** → cek HP dan **Pengiriman terakhir**.
3. Setiap pengguna yang ingin menerima WA wajib mengaktifkan sendiri (tercatat sebagai persetujuan).

---

## 4. Uji manual dari terminal (opsional)

Email (ganti nilai dalam `<>`):

```bash
curl -X POST "https://<domain-n8n>/webhook/crm-email" \
  -H "X-CRM-Webhook-Secret: <secret>" -H 'Content-Type: application/json' \
  --data '{"notification_id":"uji-1","to":"<email-anda>","subject":"Uji CRM","html":"<p>Halo</p>","sender_name":"CRM Maiharta"}'
```

WhatsApp:

```bash
curl -X POST "https://<domain-n8n>/webhook/crm-whatsapp" \
  -H "X-CRM-Webhook-Secret: <secret>" -H 'Content-Type: application/json' \
  --data '{"notification_id":"uji-2","recipient_id":"uji","project_id":"","phone_e164":"+62812xxxxxxx","text":"Uji WA CRM"}'
```

Balasan yang benar: `{"ok":true,"status":"accepted","notification_id":"...","message_id":"..."}`.

| Balasan | Arti |
| --- | --- |
| `Authorization data is wrong!` (403) | Header secret salah / tidak dikirim. |
| `webhook ... is not registered` (404) | Workflow belum Active atau path salah. |
| `ok:false ... 422` | Isi JSON tidak lengkap. |
| `ok:false ... 502` | Gmail/WAHA menolak. Cek credential Gmail atau status sesi WAHA. |

---

## 5. Arti status di "Pengiriman terakhir"

| Status | Arti |
| --- | --- |
| Diterima layanan | Gmail/WAHA mengembalikan ID pesan. Pesan sudah dikirim. |
| Tidak dikirim | Kanal server belum aktif, kontak belum ada, atau persetujuan WA belum ada. Alasan tertulis. |
| Gagal | n8n menolak atau gagal. Alasan berisi kode HTTP (lihat bagian 1). |
| Perlu diperiksa | Timeout. Cek n8n Executions sebelum mengulang agar tidak ganda. |

## 6. Variabel per service

| Service | Variabel |
| --- | --- |
| Backend CRM | `MONGO_URL`, `DB_NAME`, `CORS_ORIGINS`, `JWT_SECRET`, `SEED_PASSWORD`, `ADMIN_EMAIL`, `APP_URL`, `CLOUDINARY_*`, `EMAIL_ENABLED`, `N8N_EMAIL_WEBHOOK_URL`, `MAIL_SENDER_NAME`, `WHATSAPP_ENABLED`, `N8N_WAHA_WEBHOOK_URL`, `N8N_WAHA_WEBHOOK_SECRET` |
| n8n | Sudah dari template Railway (Postgres, `N8N_ENCRYPTION_KEY`, dll). Jangan ganti `N8N_ENCRYPTION_KEY`. |
| WAHA | Bagian 3.2 |
| Frontend Vercel | `REACT_APP_BACKEND_URL` saja. Tidak ada secret di frontend. |

## Referensi

- [WAHA quick start](https://waha.devlike.pro/docs/overview/quick-start/)
- [WAHA security / API key](https://waha.devlike.pro/docs/how-to/security/)
- [WAHA engines](https://waha.devlike.pro/docs/how-to/engines/)
- [n8n Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [n8n Gmail credential](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service/)
