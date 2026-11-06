# Panduan Deploy CRM Maiharta ke VPS IDCloudHost

Kode ini sudah disesuaikan untuk VPS: **database MySQL** dan **file upload disimpan langsung di server**. Notifikasi dikirim **langsung** dari backend: email lewat **Gmail API (Google Cloud)** dan WhatsApp lewat **Twilio**. **Tidak ada lagi n8n maupun WAHA** di server, jadi RAM lebih lega dan port 5678/3000 tidak dibuka.

```
Browser ──HTTPS──> Caddy (sertifikat SSL otomatis)
                    └─ https://IP_atau_domain → frontend React + /api → backend FastAPI → MySQL 8
backend ──HTTPS──> Gmail API (email)  ·  Twilio WhatsApp API (WA)
cron (tiap menit) → backend /api/cron/project-workspace (task berulang & pengingat)
```

> **Alamat memakai IP server.** Sertifikat HTTPS gratis untuk IP diterbitkan Let's Encrypt (berlaku 6 hari, diperpanjang otomatis oleh Caddy).
>
> **Email notifikasi butuh domain.** CRM menolak email berisi link ke alamat IP (aturan anti-phishing yang sudah ada). WhatsApp dan semua fitur lain tetap jalan dengan IP. Domain gratis: langkah 11.

---

## 0. Yang Anda perlukan
- VPS IDCloudHost (akses SSH: IP, user, password). OS disarankan **Ubuntu 22.04 / 24.04**.
- RAM minimal **2 GB**, disk minimal 20 GB.
- Kode terbaru sudah ada di GitHub: klik **Save to GitHub** di Emergent.

## 1. Masuk ke server lewat SSH
```bash
ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=20 USER@IP_SERVER
```
Password tidak terlihat saat diketik, itu normal. Jika user bukan `root`, tambahkan `sudo` di depan setiap perintah. Prompt `PS C:\...` berarti Anda masih di laptop, bukan di server.

## 2. Ambil kode dari GitHub
```bash
sudo apt-get update && sudo apt-get install -y git tmux
tmux new -s deploy
sudo git clone https://github.com/<akun>/<repo>.git /opt/crm-maiharta
cd /opt/crm-maiharta
```
`tmux` menjaga proses tetap jalan walau SSH putus. Untuk kembali ke layar tmux: `tmux attach -t deploy`.

## 3. Jalankan instalasi otomatis (server baru)
```bash
sudo bash deploy/setup.sh
```
Script akan memasang Docker, swap 2 GB dan firewall (22, 80, 443), membuat `deploy/.env` berisi password acak, lalu menjalankan MySQL, backend, frontend + Caddy dan cron. Pertama kali butuh ±10–20 menit. Semua alamat & password tersimpan di `deploy/.env` (`sudo cat deploy/.env`).

## 4. Buka CRM
- Buka `https://IP_SERVER`.
- Login **admin** dengan password `SEED_PASSWORD` dari `deploy/.env`, lalu segera ganti password. Akun seed lain (`adminproject`, `developer`, `accounting`, `client`) memakai password yang sama, jadi ganti atau nonaktifkan juga.
- Jika menit pertama browser memberi peringatan sertifikat, tunggu 1–2 menit lalu refresh.

## 5. File upload: langsung di server
Dokumen yang diupload disimpan di volume Docker `crm-maiharta_uploads` (di dalam container: `/data/uploads`). File tetap hanya bisa diunduh lewat CRM dengan pengecekan role, dan batas ukuran tetap 10 MB per file. File ini ikut dibackup oleh `deploy/backup.sh`.

## 5b. Server lama: bersihkan n8n + WAHA
Untuk server yang sebelumnya sudah memasang n8n + WAHA:
```bash
cd /opt/crm-maiharta
sudo git pull --ff-only                 # ambil kode terbaru (setelah Save to GitHub)
cd deploy && sudo bash backup.sh         # backup data CRM dulu
sudo bash hapus-n8n-waha.sh              # ketik YA saat diminta
sudo bash update.sh                      # build ulang backend & frontend versi baru
```
`hapus-n8n-waha.sh` akan: membuat backup terakhir n8n/WAHA ke `deploy/backups/sebelum-hapus-n8n-waha-<tgl>/`, menghapus container, volume dan image n8n/WAHA, menutup port 5678 & 3000 di firewall, menghapus variabel `N8N_*`/`WAHA_*` dari `deploy/.env` dan menambahkan variabel `GMAIL_*`/`TWILIO_*` yang masih kosong. **Data CRM (MySQL, file upload, sertifikat HTTPS) tidak disentuh.** Bila port 5678/3000 juga dibuka di firewall panel IDCloudHost, tutup juga di sana. Cek hasil: `sudo docker compose ps` hanya menampilkan `mysql`, `backend`, `web`, `cron`.

## 6. Aktifkan email (Gmail API, Google Cloud)
Ikuti **Panduan notifikasi** bagian A (di CRM: **Pengaturan → Panduan notifikasi**, atau file `frontend/public/panduan-notifikasi.md`) untuk mendapatkan Client ID, Client secret dan refresh token. Lalu:
```bash
cd /opt/crm-maiharta/deploy && sudo nano .env
```
```
EMAIL_ENABLED=true
GMAIL_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-xxxxxxxx
GMAIL_REFRESH_TOKEN=1//0xxxxxxxx
GMAIL_SENDER=cvmaiharta@gmail.com
```
Simpan (`Ctrl+O`, `Enter`, `Ctrl+X`), lalu `sudo docker compose up -d backend`.

## 7. Aktifkan WhatsApp (Twilio)
Masuk ke server lalu buka `.env`:
```bash
cd /opt/crm-maiharta/deploy
sudo nano .env
```
Hapus baris lama `WA_API_URL`, `WA_API_USERNAME`, `WA_API_TOKEN`, `WA_DEVICE_ID`, `WA_BODY_FORMAT`, `WA_AUTH_HEADER`, `WA_AUTH_SCHEME`, `WA_BODY_TEMPLATE`, `WA_MESSAGE_ID_PATH` (sudah tidak dipakai), lalu tambahkan (nilai dari Twilio Console, lihat panduan notifikasi bagian B):
```
WHATSAPP_ENABLED=true
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=<Auth Token Twilio>
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_CONTENT_SID=
```
Simpan (`Ctrl+O`, `Enter`, `Ctrl+X`), lalu ambil kode terbaru & jalankan ulang: `sudo bash update.sh` (atau bila kode sudah terbaru cukup `sudo docker compose up -d backend`). Cek variabel sudah masuk: `sudo docker compose exec backend printenv | grep TWILIO_ACCOUNT_SID`.

Server cukup bisa keluar ke internet (HTTPS ke `api.twilio.com`, port 443 keluar) — tidak perlu membuka port baru di firewall IDCloudHost. Selama uji coba Sandbox, setiap nomor penerima harus mengirim `join <kode>` ke nomor Sandbox dulu. Setelah berhasil, ganti ke nomor WhatsApp Business resmi: ubah `TWILIO_WHATSAPP_FROM` + isi `TWILIO_CONTENT_SID` (panduan notifikasi B.2), lalu `sudo docker compose up -d backend`.

## 8. Uji notifikasi
Di CRM: **Pengaturan → Notifikasi akun** → status provider harus **Konfigurasi tersedia** → isi nomor WA → **Uji notifikasi**. Isi pesan dan template notifikasi sama seperti sebelumnya.

## 9. Perintah harian (dari `/opt/crm-maiharta/deploy`)
| Kebutuhan | Perintah |
|---|---|
| Status layanan | `sudo docker compose ps --format "table {{.Service}}\t{{.Status}}"` |
| Log backend / SSL | `sudo docker compose logs --tail=100 backend` · `web` |
| Restart semua | `sudo docker compose restart` |
| **Update kode / build ulang** (setelah Save to GitHub atau ubah `.env`) | `sudo bash update.sh` (tetap jalan walau SSH putus; progres: `sudo tail -f update.log`) |
| Backup (DB + file upload) | `sudo bash backup.sh` → `deploy/backups/` (disimpan 3 hari terakhir) |
| **Kosongkan semua data & bersihkan server** (mulai dari awal, hanya akun `admin`) | `sudo bash reset-data.sh` |
| **Bersihkan file tidak penting** (image & cache build lama, log sistem, cache apt). Data & upload aman | `sudo bash cleanup.sh` |
| Backup otomatis tiap 02.00 | `(sudo crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/crm-maiharta/deploy && bash backup.sh >/dev/null 2>&1") \| sudo crontab -` |
| Restore database | `gunzip -c backups/<tgl>/mysql.sql.gz \| sudo docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'` |

## 10. Troubleshooting
- **`ERR_SSL_PROTOCOL_ERROR`**: `sudo docker compose logs --tail=50 web`. Pastikan port 80 terbuka (dipakai untuk verifikasi sertifikat) dan tidak ada apache/nginx lain: `sudo systemctl disable --now apache2 nginx`.
- **SSH sering putus saat build**: build frontend memakai hampir semua RAM. Selalu pakai `sudo bash update.sh`, yang tetap berjalan walau SSH putus. Upgrade RAM VPS ke 4 GB juga mengatasinya.
- **Layanan restart terus**: `sudo docker compose logs --tail=50 <nama-layanan>`.
- **Notifikasi gagal**: lihat alasan di **Uji notifikasi** / riwayat pengiriman dan tabel troubleshooting di panduan notifikasi. Log: `sudo docker compose logs --tail=100 backend`.
- **Jangan** mengubah `MYSQL_*`, `JWT_SECRET` setelah berjalan.
- **Dashboard WAHA: worker "not connected", Sessions 0, tetapi WA tetap terkirim**: sesi WhatsApp tidak hilang. API key worker yang tersimpan di browser tidak cocok (browser lain, cache dihapus, atau WAHA sempat mati saat `update.sh`). Cek dari server: `curl -s -H "X-Api-Key: $(grep ^WAHA_API_KEY .env | cut -d= -f2)" https://$(grep ^WAHA_DOMAIN .env | cut -d= -f2)/api/sessions`. Bila muncul `default` + `WORKING`, buka dashboard → ikon pensil di worker → isi API key = `WAHA_API_KEY` → Save, lalu refresh.

## Update perubahan kode (fitur baru)
1. Di Emergent klik **Save to GitHub** (repo yang dipakai server).
2. Di server: `cd /opt/crm-maiharta && sudo git remote -v` (pastikan repo sama), lalu `cd deploy && sudo bash backup.sh && sudo bash update.sh`.
3. Tidak ada variabel `.env` baru. Tabel MySQL baru (`project_reminders`, `inbox_reads`) dibuat otomatis. Notif WA reminder dikirim oleh layanan `cron` yang sudah ada, ke Admin yang mengisi nomor WA dan mengaktifkan WA di **Pengaturan → Notifikasi akun**.

## 11. Nanti pakai domain (dibutuhkan untuk email)
Gratis lewat **DuckDNS**: login di https://www.duckdns.org, buat subdomain (misal `maihartacrm`), isi **current ip** = IP server. Atau domain sendiri: buat record **A** `@` ke IP server. Lalu:
```bash
cd /opt/crm-maiharta && sudo bash deploy/change-domain.sh maihartacrm.duckdns.org
```
Hasilnya: CRM `https://maihartacrm.duckdns.org`. Setelah itu aktifkan email (langkah 6). Alamat `sslip.io` tidak disarankan karena jatah sertifikatnya sering habis.

## 12. Backup otomatis ke Google Drive (tiap 00:00, zona `TIMEZONE` di `deploy/.env`, default WITA)
Script `deploy/gdrive-backup.sh` menjalankan `backup.sh` (MySQL + file upload) ditambah salinan `deploy/.env`, menggabungkannya menjadi satu file `crm-maiharta-backup-<tanggal>.tar`, lalu **mengganti seluruh isi folder Drive** dengan backup hari itu (backup kemarin di Drive dihapus permanen). Upload memakai image Docker `rclone/rclone`, jadi tidak perlu memasang apa pun.

> Buat **folder khusus** untuk backup. Semua isi folder itu akan diganti setiap malam. File berisi `.env` (password server), jadi jangan bagikan folder ke orang lain.

### Langkah 1: siapkan Google Cloud (sekali saja)
1. Buka https://console.cloud.google.com → pilih/buat project (misal `crm-maiharta-backup`).
2. **APIs & Services → Library** → cari **Google Drive API** → **Enable**.

### Langkah 2: pilih cara login ke Drive
**Cara A: Service Account (hanya untuk Shared Drive Google Workspace).** Google tidak memberi kuota penyimpanan ke service account, jadi cara ini **hanya bisa dipakai kalau foldernya ada di Shared Drive** (akun Google Workspace berbayar). Kalau dipakai untuk "My Drive" Gmail biasa, upload gagal dengan error `storageQuotaExceeded`.
1. **IAM & Admin → Service Accounts → Create service account** (nama bebas) → **Done**.
2. Klik service account → **Keys → Add key → Create new key → JSON**. File JSON akan terunduh.
3. Di Google Drive buat Shared Drive, lalu buat folder backup di dalamnya. **Kelola anggota** → tambahkan email service account (`...@...iam.gserviceaccount.com`) sebagai **Content manager**.
4. Upload file JSON ke server (dari laptop): `scp file-key.json USER@IP_SERVER:/tmp/` lalu di server: `sudo mv /tmp/file-key.json /opt/crm-maiharta/deploy/gdrive-service-account.json && sudo chmod 600 /opt/crm-maiharta/deploy/gdrive-service-account.json`
5. Isi di `deploy/.env`: `GDRIVE_FOLDER_ID=<ID folder>` dan `GDRIVE_SHARED_DRIVE_ID=<ID Shared Drive>`.

**Cara B: Gmail biasa (misal `cvmaiharta@gmail.com`), disarankan kalau tidak punya Workspace.**
1. **APIs & Services → OAuth consent screen** → External → isi nama aplikasi & email → tambahkan email Gmail Anda di **Test users**. Lalu **Publish app** (status *In production*) supaya token tidak kedaluwarsa setiap 7 hari.
2. **Credentials → Create credentials → OAuth client ID → Desktop app** → catat **Client ID** dan **Client secret**.
3. Di **laptop** (bukan server), pasang rclone (https://rclone.org/downloads/), lalu jalankan:
   `rclone authorize "drive" "CLIENT_ID" "CLIENT_SECRET"`
   Browser terbuka → login Gmail → Allow. Terminal akan menampilkan JSON token `{"access_token":...}`. Salin satu baris JSON tersebut.
4. Isi di `deploy/.env` (token ditulis dalam tanda kutip tunggal):
```
GDRIVE_FOLDER_ID=<ID folder>
GDRIVE_CLIENT_ID=<Client ID>
GDRIVE_CLIENT_SECRET=<Client secret>
GDRIVE_TOKEN='{"access_token":"...","token_type":"Bearer","refresh_token":"...","expiry":"..."}'
```

**ID folder** = bagian terakhir URL folder di Drive, misal `https://drive.google.com/drive/folders/1AbCdEf...` → `1AbCdEf...`. ID Shared Drive juga diambil dari URL Shared Drive tersebut.

### Langkah 3: uji lalu pasang jadwal
```bash
cd /opt/crm-maiharta/deploy
sudo nano .env                              # isi variabel GDRIVE_* di atas
sudo bash gdrive-backup.sh                  # uji sekarang → cek file muncul di folder Drive
sudo bash gdrive-backup.sh --install-cron   # jadwal otomatis tiap 00:00 (systemd timer)
sudo bash gdrive-backup.sh --status         # cek jadwal berikutnya (kolom NEXT) & log terakhir
```
Jadwal memakai **systemd timer** dengan zona waktu tertulis jelas (`TIMEZONE` di `deploy/.env`), jadi tetap jalan tepat 00:00 walau jam server UTC, dan dijalankan susulan bila server mati saat tengah malam. Server yang dulu memakai jadwal crontab lama (yang terhitung 00:00 WIB = 01:00 WITA): cukup jalankan ulang `sudo bash gdrive-backup.sh --install-cron`, baris crontab lama otomatis dihapus.
**Backup ulang otomatis:** bila backup 00:00 gagal (internet/Drive bermasalah, MySQL belum siap, server mati, dll.), script meninggalkan penanda `deploy/.gdrive-backup.pending`. Timer `crm-gdrive-backup-retry` mengecek tiap 15 menit dan mengulang backup sampai berhasil, lalu penanda dihapus. Bila backup tidak gagal, timer ini tidak melakukan apa pun. Server lama: jalankan ulang `sudo bash gdrive-backup.sh --install-cron` sekali agar timer ini terpasang. `--status` menampilkan apakah backup terakhir berhasil atau masih menunggu diulang.
Log setiap malam: `sudo tail -50 /opt/crm-maiharta/deploy/gdrive-backup.log`. Jika sebelumnya memasang cron `backup.sh` jam 02.00 (langkah 9), boleh dihapus dengan `sudo crontab -e` karena backup lokal sudah ikut dibuat oleh script ini (salinan lokal tetap disimpan 3 hari di `deploy/backups/`).

### Restore dari Drive
Unduh file `.tar` dari Drive ke server, lalu: `mkdir -p /tmp/restore && tar xf crm-maiharta-backup-*.tar -C /tmp/restore`. Database: `gunzip -c /tmp/restore/mysql.sql.gz | sudo docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'`. Volume file (contoh uploads): `sudo docker run --rm -v crm-maiharta_uploads:/data -v /tmp/restore:/in alpine sh -c 'tar xzf /in/uploads.tar.gz -C /data'`. `env.txt` adalah salinan `deploy/.env`.

## 13. Jeda notifikasi & reset password (Manajemen user)
- **Jeda semua akun**: panel di atas tabel **Manajemen user** → sakelar Email / WhatsApp. Saat dijeda, email & WA tidak dikirim ke akun mana pun (notifikasi in-app tetap ada).
- **Jeda per akun**: kolom **Notif** → klik ikon amplop (email) / chat (WA). Ikon merah bercoret = dijeda.
- **Reset password ke default** (ikon kunci): password kembali ke `12345678`, semua sesi akun keluar, dan pengguna wajib membuat password baru saat login. Username & password langsung dikirim ke email dan WhatsApp akun tersebut memakai template notifikasi yang sama, **walaupun notifikasi sedang dijeda**.
- Agar email tidak masuk Spam: kirim lewat Gmail API (sudah memakai versi teks + HTML, header List-Unsubscribe dan tautan HTTPS ke domain CRM), pakai domain (bukan IP) di `APP_URL`, dan minta penerima menandai email pertama sebagai **Bukan spam** / menambahkan alamat pengirim ke kontak.
- Tidak ada variabel `.env` baru untuk fitur ini. Pengaturan jeda disimpan otomatis di tabel MySQL baru `app_settings`.

## Catatan teknis perubahan kode
- `backend/docstore.py`: lapisan penyimpanan MySQL yang perilakunya sama seperti MongoDB sebelumnya. Setiap koleksi menjadi satu tabel, dibuat otomatis.
- `backend/core.py` memakai `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`. Logika fitur, API dan frontend tidak berubah.
- `backend/storage.py`: tanpa Cloudinary, file disimpan di `UPLOAD_DIR` (disk server).
- Cron Railway diganti layanan `cron` di `deploy/docker-compose.yml`.

## 14. Menghubungkan ChatGPT/Claude (Asisten AI + MCP)

1. Login sebagai **Admin** → **Pengaturan → Fitur AI & MCP** → nyalakan sakelar. Satu sakelar ini mengaktifkan/menonaktifkan semua fitur AI (panel Asisten AI, Token API, server MCP, OAuth). Bisa dikunci mati dari server dengan `AI_ENABLED="false"` di `backend/.env`.
2. Isi provider AI OpenAI-compatible (default SumoPod): `AI_BASE_URL` (mis. `https://ai.sumopod.com/v1`), `AI_MODEL`, `AI_API_KEY` — lewat form admin atau di `backend/.env`. Jangan pernah menaruh API key di repo/README/setup.sh. Tanpa API key, panel Asisten menampilkan pesan nonaktif.
3. **Claude Desktop / Cursor / MCP Inspector**: tiap user membuat token di **Pengaturan → Token API & koneksi AI** (scope `read` atau `read + write`, maks. 10 token). Token hanya tampil sekali dan disimpan dalam bentuk hash.
   - URL server MCP: `https://<domain>/api/mcp` (Streamable HTTP, JSON-RPC).
   - Header: `Authorization: Bearer mh_pat_...`
   - Contoh Claude Desktop (`claude_desktop_config.json`): `{"mcpServers":{"crm":{"command":"npx","args":["-y","mcp-remote","https://<domain>/api/mcp","--header","Authorization: Bearer mh_pat_xxx"]}}}`
   - Uji cepat: `curl -H "Authorization: Bearer mh_pat_xxx" https://<domain>/api/ai/tools/tugas_saya`
4. **ChatGPT (Developer mode → Connectors)**: masukkan URL `https://<domain>/api/mcp`, pilih autentikasi **OAuth**. ChatGPT mendaftar otomatis (Dynamic Client Registration), lalu membuka halaman persetujuan CRM — login dan klik **Izinkan**. Metadata: `https://<domain>/api/.well-known/oauth-protected-resource` dan `https://<domain>/api/.well-known/oauth-authorization-server`.
5. Mencabut akses: user di **Pengaturan → Token API**, atau Admin di **Pengaturan → Fitur AI & MCP → Semua token**. Token yang dicabut langsung mendapat 401. Semua pembuatan/pencabutan token dan aksi tulis AI tercatat di **Audit Trail**.
