# CRM Maiharta

Sistem manajemen project MaiHarta — React + FastAPI + MySQL, di-deploy ke VPS IDCloudHost dengan Docker (notifikasi langsung via Gmail API & WhatsApp API, file upload disimpan di server).

**Panduan deploy VPS: [DEPLOY_IDCLOUDHOST.md](DEPLOY_IDCLOUDHOST.md)** (`bash deploy/setup.sh`).

Bagian Railway/Vercel/MongoDB di bawah adalah catatan lama dan tidak dipakai lagi.

## Setup lokal
`bash setup.sh` (sekali), lalu `bash start-local.sh` (Windows CMD: `start-local.bat`). Butuh Python 3.11+, Node 18+, MySQL/MariaDB yang berjalan, dan openssl.

## Notifikasi web & aplikasi terpasang (PWA)
- Semua notifikasi di lonceng CRM juga dikirim sebagai notifikasi web ke Windows, macOS, Android, dan iOS/iPadOS 16.4+ (setelah CRM ditambahkan ke Layar Utama).
- Aktifkan per perangkat di **Pengaturan → Notifikasi akun → Notifikasi web di perangkat ini**. Di sana juga ada tombol/petunjuk **Pasang aplikasi CRM**.
- Kunci VAPID dibuat otomatis oleh `deploy/setup.sh`, `deploy/update.sh` dan `setup.sh` (`deploy/vapid.sh`). Jangan diganti setelah dipakai, karena semua perangkat harus mengaktifkan ulang.
- Notifikasi web wajib HTTPS (kecuali `localhost`).

## MCP wajib OAuth
`/api/mcp` hanya menerima access token OAuth. Token API pribadi (`mh_pat_`) ditolak di MCP dan hanya berlaku untuk REST API.

## Akun awal (seed)
Password akun awal dibaca dari variabel backend `SEED_PASSWORD` saat database kosong. Tidak ada password produksi yang disimpan di repositori. Ganti password melalui Pengaturan setelah login.

| Role          | Username       |
|---------------|----------------|
| Admin         | `admin`        |
| Admin Project | `adminproject` |
| Developer     | `developer`    |
| Accounting    | `accounting`   |
| Client        | `client`       |

## Deploy backend ke Railway
1. New Project → Deploy from GitHub repo → pilih repo ini.
2. Settings → **Root Directory**: `backend`.
3. Variables (lihat `backend/.env.example`):
   - `MONGO_URL` — connection string MongoDB Atlas
   - `DB_NAME` — misal `crm_maiharta`
   - `CORS_ORIGINS` — URL frontend Vercel, dipisah koma (misal `https://crm-maiharta.vercel.app`)
   - `JWT_SECRET` — string acak panjang
   - `SEED_PASSWORD`, `ADMIN_EMAIL`
   - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
   - Email Gmail API: `EMAIL_ENABLED`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER`, `MAIL_SENDER_NAME`, `APP_URL`
   - WhatsApp Twilio: `WHATSAPP_ENABLED`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_CONTENT_SID` (opsional) (lihat panduan notifikasi)
4. Railway otomatis memakai `backend/railway.json` (start: `uvicorn server:app --host 0.0.0.0 --port $PORT`, healthcheck `/api/health`).
5. Generate Domain → catat URL, misal `https://crm-maiharta-backend.up.railway.app`.

## Deploy frontend ke Vercel
1. Import repo → **Root Directory**: `frontend` (Framework: Create React App).
2. Environment Variable: `REACT_APP_BACKEND_URL` = URL Railway di atas (tanpa `/api`, tanpa slash di akhir).
3. Deploy. `frontend/vercel.json` sudah mengatur SPA rewrite dan `CI=false`.
4. Setelah domain Vercel aktif, tambahkan domain tersebut ke `CORS_ORIGINS` di Railway lalu redeploy backend.

### Pengaturan publik tautan bantuan
- `frontend/.env.production` sengaja disertakan dalam repository dan hanya berisi `REACT_APP_CONTACT_EMAIL=cvmaiharta@gmail.com` serta `REACT_APP_CONTACT_COMPOSE_URL=https://mail.google.com/mail/`. CRA memuatnya otomatis untuk build production; tidak bergantung pada file `.env` lokal yang diabaikan Git.
- Jangan memasukkan password, token, JWT secret atau koneksi database ke file publik tersebut. File `.env` lokal dan file rahasia lainnya tetap diabaikan Git.
- Environment Variable yang diatur langsung di Vercel memiliki prioritas lebih tinggi. Jika ada override untuk dua pengaturan bantuan ini, isikan nilai yang benar; jangan isi kosong.
- Konfigurasi bantuan yang hilang/salah hanya menonaktifkan tautan dengan pemberitahuan; tidak boleh menghentikan halaman login. Tes regresi: `cd frontend && yarn test --watchAll=false --runTestsByPath src/lib/contact.test.js`.
- Bila build berstatus Ready tetapi halaman lama masih putih dengan error `Invalid URL`, pastikan build terbaru memakai commit yang sudah mengandung `ContactLink.jsx`, `lib/contact.js` dan `.env.production`, bukan membangun ulang commit lama yang masih memanggil `new URL(...)` langsung saat import.

## Notifikasi email dan WhatsApp

Setiap akun mengatur kanal di **Pengaturan → Notifikasi akun**. Email dikirim **langsung lewat Gmail API (Google Cloud)** memakai OAuth refresh token akun Gmail pengirim; WhatsApp dikirim **lewat Twilio WhatsApp** (Messages API, variabel `TWILIO_*`). Tidak ada n8n/WAHA. Template, isi pesan dan aturan notifikasi tidak berubah. Kanal eksternal tetap nonaktif sampai konfigurasi siap. Tidak ada secret provider pada frontend.

Panduan lengkap: buka `/settings/notifications-guide` di CRM atau baca [Panduan notifikasi](frontend/public/panduan-notifikasi.md).

## Backup data

Di VPS: `bash deploy/backup.sh` (MySQL + file upload). Di luar Docker: `bash scripts/backup_mysql.sh DIREKTORI_BARU`. Database lama pengguna tidak diakses dalam perubahan ini. Fitur impor ClickUp telah dihapus (halaman, API, contoh CSV dan panduan impor); task yang dahulu sudah diimpor tidak dihapus.

## Link berbagi file
- Tombol **Bagikan** (ikon share) pada dokumen project dan lampiran task membuat link publik `/s/<token>`.
- **Banyak dokumen dalam 1 link**: di tab Dokumen project, centang beberapa dokumen (atau "pilih semua") → **Bagikan N dokumen**. Penerima melihat daftar semua dokumen di satu halaman, masing-masing bisa dilihat/diunduh.
- **Password (opsional)**: saat membuat link pilih *Tanpa password* atau *Pakai password* (min. 4 karakter). Penerima harus memasukkan password sebelum melihat isi. 10x salah → dikunci 15 menit.
- Masa berlaku: 1 jam, 1 hari, 7 hari, 30 hari, tanggal/jam sendiri (maks. 365 hari), atau **Tanpa batas**. Mode **Hanya lihat** atau **Lihat & download**. Link bisa dicabut kapan saja.
- API: `POST /api/shares` (`document_ids`, `expires_at` boleh `null`, `allow_download`, `password`), `GET /api/shares?document_id=`, `DELETE /api/shares/{id}`, publik `GET /api/public/shares/{token}?k=`, `POST /api/public/shares/{token}/unlock`, `/file?doc=<id>&download=true&k=`.

## MCP: tambahan
- Melalui MCP/token API, project berstatus **Selesai** tanpa maintenance aktif tidak dapat dibaca (tidak muncul di daftar, task, notes, dokumen). Asisten di dalam aplikasi tidak berubah.
- Tools baru: `opsi_form`, `tambah_tugas`, `tambah_maintenance` (project harus Selesai), `upload_lampiran_tugas`, `upload_dokumen_project` (file dalam base64, maks. 10 MB), `daftar_dokumen`, `bagikan_file`.
- `tambah_tugas` memakai isian yang sama dengan form Task baru: judul, status, server, penanggung jawab (bisa lebih dari satu), prioritas, list, tanggal mulai, target selesai, estimasi jam, tag, deskripsi, subtask bertingkat, lampiran.
- `tambah_maintenance` memakai isian yang sama dengan form Maintenance baru: judul, klasifikasi, prioritas, tanggal masuk (wajib), grup, tanggal dikerjakan, target selesai, penanggung jawab, estimasi biaya, deskripsi, subtask bertingkat, lampiran.
- `opsi_form` menampilkan pilihan valid (status, list, grup, penanggung jawab) agar asisten AI menanyakan isian dengan benar.

## Catatan
- Sesi login memakai token Bearer (localStorage) + cookie `SameSite=None; Secure`, sehingga aman lintas domain Vercel ↔ Railway.
- Dokumen project disimpan di Cloudinary (`resource_type=raw`, `type=authenticated`) dan diunduh melalui backend dengan pengecekan role.
- Data awal (5 akun, 5 client, 8 project) dibuat otomatis saat backend pertama kali berjalan pada database kosong.

## Akun client baru
- Saat menambah melalui **Client → Client baru**, akun login dibuat otomatis jika username email tersebut belum ada.
- **Username:** alamat email client. **Password awal:** `12345678`.
- Akun otomatis ditandai wajib mengganti password saat pertama masuk. Password baru minimal 10 karakter.
- Jika email sudah digunakan akun lain, proses tambah client tidak membuat akun pengganti dan tidak mereset password akun tersebut.
- Akun yang dibuat melalui **Manajemen User** menggunakan password yang diisi admin, bukan password default di atas. Akun seed `client` juga berbeda.

## Dependensi backend yang portabel
- `backend/requirements.in` berisi dependensi runtime langsung; `backend/requirements.txt` adalah hasil instalasi dan freeze dalam virtual environment bersih.
- Jika perlu memperbarui dependensi, ubah versi di `requirements.in`, lalu jalankan `bash scripts/lock_backend_requirements.sh` dari repository ini.
- Jangan menjalankan `pip freeze` dari lingkungan pengembangan bersama: paket internal seperti `emergentintegrations` atau URL wheel privat dapat ikut masuk dan membuat instalasi publik gagal.
- Script memeriksa kompatibilitas dengan `pip check` dan hanya menggunakan indeks paket publik. Instalasi aplikasi tetap menggunakan `pip install -r backend/requirements.txt`.
