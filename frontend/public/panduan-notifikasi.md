# Panduan Notifikasi Email & WhatsApp

CRM mengirim notifikasi **langsung** dari backend, tanpa n8n dan tanpa WAHA:

- **Email** → **Gmail API (Google Cloud)** memakai akun Gmail pengirim (misal `cvmaiharta@gmail.com`).
- **WhatsApp** → **WhatsApp API** provider Anda (format request mengikuti koleksi Postman dari provider).

Isi, template dan aturan notifikasi **tidak berubah**: subjek, isi email (HTML + teks), teks WhatsApp, preferensi per akun, jeda global/per akun, uji notifikasi, dan riwayat pengiriman tetap sama. Yang diganti hanya "jalur kirimnya".

Semua kredensial disimpan di **server** (`deploy/.env` di VPS atau `backend/.env` saat lokal). Tidak ada secret di frontend atau repo.

---

## A. Email via Gmail API (Google Cloud)

### 1. Buat project & aktifkan Gmail API
1. Buka https://console.cloud.google.com → **Select project → New project** (misal `crm-maiharta-mail`).
2. **APIs & Services → Library** → cari **Gmail API** → **Enable**.

### 2. OAuth consent screen
1. **APIs & Services → OAuth consent screen** (atau **Google Auth Platform → Branding**) → **External**.
2. Isi nama aplikasi (`CRM Maiharta`), email dukungan & email developer.
3. **Audience / Test users** → tambahkan Gmail pengirim (misal `cvmaiharta@gmail.com`).
4. **Data access / Scopes** → tambahkan `https://www.googleapis.com/auth/gmail.send`.
5. Klik **Publish app** (status **In production**). Penting: kalau tetap *Testing*, refresh token kedaluwarsa setiap 7 hari dan email berhenti terkirim. Peringatan "app belum diverifikasi" boleh diabaikan karena hanya Anda sendiri yang login.

### 3. Buat OAuth Client
1. **APIs & Services → Credentials → Create credentials → OAuth client ID**.
2. Application type: **Web application**.
3. **Authorized redirect URIs**: `https://developers.google.com/oauthplayground`
4. **Create** → catat **Client ID** dan **Client secret**.

### 4. Ambil refresh token (OAuth Playground)
1. Buka https://developers.google.com/oauthplayground
2. Klik ikon ⚙️ (kanan atas) → centang **Use your own OAuth credentials** → isi Client ID & Client secret dari langkah 3.
3. Di kolom kiri ketik scope: `https://www.googleapis.com/auth/gmail.send` → **Authorize APIs**.
4. Login dengan Gmail pengirim → **Continue/Allow**.
5. Klik **Exchange authorization code for tokens** → salin **Refresh token** (diawali `1//`).

### 5. Isi konfigurasi server
```
EMAIL_ENABLED=true
GMAIL_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-xxxxxxxx
GMAIL_REFRESH_TOKEN=1//0xxxxxxxx
GMAIL_SENDER=cvmaiharta@gmail.com
MAIL_SENDER_NAME=CRM Maiharta
```
`GMAIL_SENDER` harus sama dengan akun Gmail yang login di langkah 4.

> Email berisi link ke CRM, dan aturan anti-phishing CRM menolak link ke alamat IP. Jadi **email butuh `APP_URL` berupa domain** (misal DuckDNS gratis, lihat DEPLOY_IDCLOUDHOST.md). WhatsApp tetap jalan dengan IP.

---

## B. WhatsApp via Twilio

### B.1 Uji coba dengan Twilio Sandbox (gratis)
1. Daftar / login di https://console.twilio.com.
2. Di halaman utama Console, salin **Account SID** (diawali `AC...`) dan **Auth Token** (klik *Show*).
3. Buka **Messaging → Try it out → Send a WhatsApp message**. Catat nomor Sandbox (biasanya `+1 415 523 8886`) dan kode join (misal `join kata-unik`).
4. Dari **setiap HP penerima** (nomor yang diisi di CRM), kirim pesan WhatsApp `join kata-unik` ke nomor Sandbox. Tunggu balasan "You are all set!".
5. Isi di `.env` server:
```
WHATSAPP_ENABLED=true
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=<Auth Token dari Console>
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_CONTENT_SID=
```
- Catatan Sandbox: penerima wajib join dulu (kalau belum: error `63015`). Pesan teks bebas hanya terkirim bila penerima mengirim pesan ke nomor Sandbox dalam 24 jam terakhir; balas/kirim pesan apa saja ke Sandbox bila pesan tidak masuk. Sesi join Sandbox berakhir setelah 3 hari tidak aktif, cukup kirim `join kata-unik` lagi.

### B.2 Pindah ke nomor WhatsApp Business resmi (produksi)
1. Twilio Console → **Messaging → Senders → WhatsApp senders → Create new sender**, ikuti verifikasi Meta Business dan nomor HP (nomor tidak boleh sedang dipakai di aplikasi WhatsApp biasa).
2. Buat template di **Messaging → Content Template Builder**: kategori *Utility*, isi body misal `Notifikasi CRM Maiharta: {{1}}`, lalu *Submit for WhatsApp approval*. Setelah *Approved*, salin **Content SID** (`HX...`).
3. Ubah `.env`:
```
TWILIO_WHATSAPP_FROM=whatsapp:+62xxxxxxxxxx
TWILIO_CONTENT_SID=HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
Bila `TWILIO_CONTENT_SID` diisi, isi notifikasi CRM dikirim sebagai variabel `{{1}}` template (baris baru diganti tanda ` · `), sehingga tetap terkirim walau di luar jendela 24 jam.

<details><summary>Opsional</summary>

| Variabel | Isi |
|---|---|
| `TWILIO_API_KEY_SID` / `TWILIO_API_KEY_SECRET` | Pakai API Key (`SK...`) sebagai pengganti Auth Token (lebih aman, bisa dicabut terpisah) |
| `TWILIO_STATUS_CALLBACK` | URL HTTPS untuk menerima status kirim dari Twilio (boleh kosong) |
</details>

- Nomor `08...` / `62...` di CRM dikonversi otomatis menjadi `+62...`. Isi pesan WhatsApp sama seperti sebelumnya.

---

## C. Terapkan & uji
- **VPS**: `cd /opt/crm-maiharta/deploy && sudo nano .env` → isi variabel di atas → `sudo docker compose up -d backend`.
- **Lokal**: isi `backend/.env` → restart backend (`./start-local.sh`).
- Di CRM: **Pengaturan → Notifikasi akun** → status provider harus **Konfigurasi tersedia** → isi nomor WA → **Uji notifikasi**.

## D. Troubleshooting
| Pesan | Arti / solusi |
|---|---|
| `Konfigurasi Gmail API belum lengkap: ...` | Ada variabel `GMAIL_*` atau `APP_URL` yang kosong. |
| `Google menolak refresh token (invalid_grant)` | Refresh token kedaluwarsa/dicabut. Pastikan app sudah **In production**, lalu ulangi langkah A.4. |
| `Gmail API menolak kredensial (HTTP 403)` | Gmail API belum di-*Enable* atau scope `gmail.send` belum diberikan. |
| `Email links/assets must be absolute https` / `numeric-host` | `APP_URL` masih IP. Pakai domain. |
| `Twilio WhatsApp menolak kredensial (HTTP 401/403)` | Cek `TWILIO_ACCOUNT_SID` dan `TWILIO_AUTH_TOKEN` (atau API Key). |
| `Nomor penerima belum join Twilio Sandbox` | Kirim `join <kode>` dari WA penerima ke nomor Sandbox. |
| `Di luar jendela 24 jam WhatsApp` | Isi `TWILIO_CONTENT_SID` dengan template yang sudah disetujui, atau (Sandbox) kirim pesan dulu ke nomor Sandbox. |
| `TWILIO_WHATSAPP_FROM harus berformat ...` | Tulis `whatsapp:+14155238886` (pakai `whatsapp:` dan `+`). |

"Diterima layanan" berarti Gmail/provider WhatsApp sudah menerima pesan untuk dikirim, belum tentu sudah dibaca penerima. Ikuti persetujuan penerima dan kebijakan provider WhatsApp Anda.
