# Panduan Deploy CRM Maiharta ke VPS IDCloudHost

Kode ini sudah disesuaikan untuk VPS: **database MySQL**, **file upload disimpan langsung di server**, serta **n8n + WAHA berjalan di VPS yang sama**. Semua fitur CRM tetap sama seperti versi Railway.

```
Browser ──HTTPS──> Caddy (sertifikat SSL otomatis untuk IP server)
                    ├─ https://IP          → frontend React + /api → backend FastAPI → MySQL 8
                    ├─ https://IP:5678     → n8n (WhatsApp & Email)
                    └─ https://IP:3000     → WAHA (WhatsApp, scan QR)
cron (tiap menit) → backend /api/cron/project-workspace (task berulang & pengingat)
```

> **Alamat memakai IP server.** Sertifikat HTTPS gratis untuk IP diterbitkan Let's Encrypt (berlaku 6 hari, diperpanjang otomatis oleh Caddy). HTTPS wajib karena login, notifikasi dan webhook n8n hanya berjalan lewat HTTPS.
>
> **Email notifikasi butuh domain.** Google tidak mengizinkan login Gmail di n8n dari alamat IP, dan CRM menolak email berisi link ke alamat IP (aturan anti-phishing yang sudah ada). Notifikasi WhatsApp dan semua fitur lain tetap jalan dengan IP. Kalau email dibutuhkan nanti, lihat langkah 11.

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

## 3. Jalankan instalasi otomatis
```bash
sudo sed -i 's/WAHA_ENGINE=WEBJS/WAHA_ENGINE=NOWEB/' deploy/setup.sh   # mode WhatsApp hemat RAM
sudo bash deploy/setup.sh
```
Script akan memasang Docker, swap 2 GB dan firewall (22, 80, 443, 5678, 3000), membuat `deploy/.env` berisi password acak, lalu menjalankan MySQL, backend, frontend + Caddy, n8n, WAHA dan cron. Pertama kali butuh ±10–20 menit. Semua alamat & password tersimpan di `deploy/.env` (`sudo cat deploy/.env`).

Server yang sudah terpasang dengan alamat lama (sslip.io)? Pindah ke IP dengan: `sudo bash deploy/change-domain.sh IP_SERVER`.

## 4. Buka CRM
- Buka `https://IP_SERVER` (contoh `https://IP_SERVER`).
- Login **admin** dengan password `SEED_PASSWORD` dari `deploy/.env`, lalu segera ganti password. Akun seed lain (`adminproject`, `developer`, `accounting`, `client`) memakai password yang sama, jadi ganti atau nonaktifkan juga.
- Jika menit pertama browser memberi peringatan sertifikat, tunggu 1–2 menit lalu refresh.

## 5. File upload: langsung di server
Dokumen yang diupload disimpan di volume Docker `crm-maiharta_uploads` (di dalam container: `/data/uploads`). File tetap hanya bisa diunduh lewat CRM dengan pengecekan role, dan batas ukuran tetap 10 MB per file. File ini ikut dibackup oleh `deploy/backup.sh`.

## 6. WAHA (WhatsApp): scan QR
1. Buka `https://IP_SERVER:3000/dashboard`, login `admin` + `WAHA_DASHBOARD_PASSWORD`.
2. Bila diminta server/API key: URL `https://IP_SERVER:3000`, API key = `WAHA_API_KEY`.
3. Start session **`default`**, lalu scan QR dari WhatsApp di HP (*Perangkat tertaut → Tautkan perangkat*). Tunggu status **WORKING**.

## 7. n8n: workflow WhatsApp
1. Buka `https://IP_SERVER:5678` → buat akun owner n8n.
2. Download template `https://IP_SERVER/n8n-waha-workflow.json`, lalu di n8n: **Workflows → Import from file**.
3. Credential **Header Auth** `CRM Webhook Secret`: Name `X-CRM-Webhook-Secret`, Value = `N8N_WAHA_WEBHOOK_SECRET`. Pilih di node **Webhook CRM**.
4. Node **Konfigurasi WAHA**: `waha_base_url` = `http://waha:3000`, `waha_session` = `default`.
5. Node **Kirim via WAHA**: credential **Header Auth** Name `X-Api-Key`, Value = `WAHA_API_KEY`.
6. **Publish/Activate**. URL produksinya: `https://IP_SERVER:5678/webhook/crm-whatsapp`.

## 8. Aktifkan notifikasi WhatsApp di CRM
```bash
cd /opt/crm-maiharta/deploy && sudo nano .env
```
Ubah:
```
WHATSAPP_ENABLED=true
N8N_WAHA_WEBHOOK_URL=https://IP_SERVER:5678/webhook/crm-whatsapp
```
Simpan (`Ctrl+O`, `Enter`, `Ctrl+X`), lalu `sudo docker compose up -d backend`. Di CRM: **Pengaturan → Notifikasi akun** → isi nomor → **Kirim uji**.

## 9. Perintah harian (dari `/opt/crm-maiharta/deploy`)
| Kebutuhan | Perintah |
|---|---|
| Status layanan | `sudo docker compose ps --format "table {{.Service}}\t{{.Status}}"` |
| Log backend / n8n / WAHA / SSL | `sudo docker compose logs --tail=100 backend` · `n8n` · `waha` · `web` |
| Restart semua | `sudo docker compose restart` |
| **Update kode / build ulang** (setelah Save to GitHub atau ubah `.env`) | `sudo bash update.sh` (tetap jalan walau SSH putus; progres: `sudo tail -f update.log`) |
| Backup (DB + file + n8n + WAHA) | `sudo bash backup.sh` → `deploy/backups/` |
| **Kosongkan semua data & bersihkan server** (mulai dari awal, hanya akun `admin`) | `sudo bash reset-data.sh` |
| Backup otomatis tiap 02.00 | `(sudo crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/crm-maiharta/deploy && bash backup.sh >/dev/null 2>&1") \| sudo crontab -` |
| Restore database | `gunzip -c backups/<tgl>/mysql.sql.gz \| sudo docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'` |

## 10. Troubleshooting
- **`ERR_SSL_PROTOCOL_ERROR`**: `sudo docker compose logs --tail=50 web`. Pastikan port 80 terbuka (dipakai untuk verifikasi sertifikat) dan tidak ada apache/nginx lain: `sudo systemctl disable --now apache2 nginx`.
- **n8n / WAHA tidak bisa dibuka**: pastikan port 5678 & 3000 terbuka: `sudo ufw allow 5678/tcp && sudo ufw allow 3000/tcp`, dan juga di firewall panel IDCloudHost bila ada.
- **SSH sering putus saat build**: build frontend memakai hampir semua RAM. Selalu pakai `sudo bash update.sh`, yang tetap berjalan walau SSH putus dan menghentikan n8n/WAHA sementara supaya RAM cukup. Upgrade RAM VPS ke 4 GB juga mengatasinya.
- **Layanan restart terus**: `sudo docker compose logs --tail=50 <nama-layanan>`.
- **Notifikasi gagal**: n8n → *Executions*. `401/403` = secret berbeda; `404` = workflow belum Active; WAHA error = sesi belum WORKING.
- **Jangan** mengubah `N8N_ENCRYPTION_KEY`, `MYSQL_*`, `JWT_SECRET` setelah berjalan.
- **Dashboard WAHA: worker "not connected", Sessions 0, tetapi WA tetap terkirim**: sesi WhatsApp tidak hilang. API key worker yang tersimpan di browser tidak cocok (browser lain, cache dihapus, atau WAHA sempat mati saat `update.sh`). Cek dari server: `curl -s -H "X-Api-Key: $(grep ^WAHA_API_KEY .env | cut -d= -f2)" https://$(grep ^WAHA_DOMAIN .env | cut -d= -f2)/api/sessions`. Bila muncul `default` + `WORKING`, buka dashboard → ikon pensil di worker → isi API key = `WAHA_API_KEY` → Save, lalu refresh.

## Update perubahan kode (fitur baru)
1. Di Emergent klik **Save to GitHub** (repo yang dipakai server).
2. Di server: `cd /opt/crm-maiharta && sudo git remote -v` (pastikan repo sama), lalu `cd deploy && sudo bash backup.sh && sudo bash update.sh`.
3. Tidak ada variabel `.env` baru. Tabel MySQL baru (`project_reminders`, `inbox_reads`) dibuat otomatis. Notif WA reminder dikirim oleh layanan `cron` yang sudah ada, ke Admin yang mengisi nomor WA dan mengaktifkan WA di **Pengaturan → Notifikasi akun**.

## 11. Nanti pakai domain (dibutuhkan untuk email)
Gratis lewat **DuckDNS**: login di https://www.duckdns.org, buat subdomain (misal `maihartacrm`), isi **current ip** = IP server. Atau domain sendiri: buat record **A** `@` dan **A** `*` ke IP server. Lalu:
```bash
cd /opt/crm-maiharta && sudo bash deploy/change-domain.sh maihartacrm.duckdns.org
```
Hasilnya: CRM `https://maihartacrm.duckdns.org`, n8n `https://n8n.maihartacrm.duckdns.org`, WAHA `https://waha.maihartacrm.duckdns.org`. Script ini juga memperbarui URL webhook di `.env`. Setelah itu workflow Gmail bisa disiapkan: import `n8n-gmail-workflow.json`, buat credential Gmail OAuth2 dengan redirect `https://n8n.<domain>/rest/oauth2-credential/callback`, aktifkan, lalu set `EMAIL_ENABLED=true` dan `N8N_EMAIL_WEBHOOK_URL=https://n8n.<domain>/webhook/crm-email`. Alamat `sslip.io` tidak disarankan karena jatah sertifikatnya sering habis.

## 12. Backup otomatis ke Google Drive (tiap 00:00 WIB)
Script `deploy/gdrive-backup.sh` menjalankan `backup.sh` (MySQL + file upload + n8n + sesi WAHA) ditambah salinan `deploy/.env`, menggabungkannya menjadi satu file `crm-maiharta-backup-<tanggal>.tar`, lalu **mengganti seluruh isi folder Drive** dengan backup hari itu (backup kemarin di Drive dihapus permanen). Upload memakai image Docker `rclone/rclone`, jadi tidak perlu memasang apa pun.

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
sudo bash gdrive-backup.sh --install-cron   # jadwal otomatis tiap 00:00 WIB
sudo crontab -l                             # pastikan baris gdrive-backup.sh ada
```
Log setiap malam: `sudo tail -50 /opt/crm-maiharta/deploy/gdrive-backup.log`. Jika sebelumnya memasang cron `backup.sh` jam 02.00 (langkah 9), boleh dihapus dengan `sudo crontab -e` karena backup lokal sudah ikut dibuat oleh script ini (salinan lokal tetap disimpan 14 hari di `deploy/backups/`).

### Restore dari Drive
Unduh file `.tar` dari Drive ke server, lalu: `mkdir -p /tmp/restore && tar xf crm-maiharta-backup-*.tar -C /tmp/restore`. Database: `gunzip -c /tmp/restore/mysql.sql.gz | sudo docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'`. Volume file (contoh uploads): `sudo docker run --rm -v crm-maiharta_uploads:/data -v /tmp/restore:/in alpine sh -c 'tar xzf /in/uploads.tar.gz -C /data'` (ulangi untuk `n8n_data` dan `waha_sessions`). `env.txt` adalah salinan `deploy/.env`.

## 13. Jeda notifikasi & reset password (Manajemen user)
- **Jeda semua akun**: panel di atas tabel **Manajemen user** → sakelar Email / WhatsApp. Saat dijeda, email & WA tidak dikirim ke akun mana pun (notifikasi in-app tetap ada).
- **Jeda per akun**: kolom **Notif** → klik ikon amplop (email) / chat (WA). Ikon merah bercoret = dijeda.
- **Reset password ke default** (ikon kunci): password kembali ke `12345678`, semua sesi akun keluar, dan pengguna wajib membuat password baru saat login. Username & password langsung dikirim ke email dan WhatsApp akun tersebut memakai template notifikasi yang sama, **walaupun notifikasi sedang dijeda**.
- Agar email tidak masuk Spam: kirim dari Gmail via workflow n8n yang sudah ada (sudah memakai versi teks + HTML dan tautan HTTPS ke domain CRM), pakai domain (bukan IP) di `APP_URL`, dan minta penerima menandai email pertama sebagai **Bukan spam** / menambahkan alamat pengirim ke kontak.
- Tidak ada variabel `.env` baru untuk fitur ini. Pengaturan jeda disimpan otomatis di tabel MySQL baru `app_settings`.

## Catatan teknis perubahan kode
- `backend/docstore.py`: lapisan penyimpanan MySQL yang perilakunya sama seperti MongoDB sebelumnya. Setiap koleksi menjadi satu tabel, dibuat otomatis.
- `backend/core.py` memakai `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`. Logika fitur, API dan frontend tidak berubah.
- `backend/storage.py`: tanpa Cloudinary, file disimpan di `UPLOAD_DIR` (disk server).
- Cron Railway diganti layanan `cron` di `deploy/docker-compose.yml`.
