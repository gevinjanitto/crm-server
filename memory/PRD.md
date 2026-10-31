# PRD – Perbaikan WhatsApp Twilio (crm-server)

## Masalah asli
Clone https://github.com/gevinjanitto/crm-server dan cari tahu kenapa muncul error "Twilio menolak pesan (HTTP 400, kode 21654): ContentSid Required".

## Penyebab
Tanpa TWILIO_CONTENT_SID, aplikasi mengirim WhatsApp sebagai teks bebas (Body). Akun Twilio Trial/WhatsApp Business di luar jendela 24 jam wajib memakai Content Template (HX…), jadi Twilio menolak dengan kode 21654.

## Sudah dikerjakan (Jun 2026) – di /app/crm-server
- backend/whatsapp_template.py: template Twilio yang mengikuti struktur whatsapp_text (6 variabel), membuat Content + mengajukan persetujuan WhatsApp (UTILITY, id), cek status
- backend/whatsapp_templates.py: GET /api/admin/whatsapp-template, POST /sync, POST /refresh (Admin saja), disimpan di app_settings id=whatsapp_template
- notification_delivery: kalau template sudah disetujui → kirim dengan ContentSid + ContentVariables
- whatsapp.py: penjelasan error dalam bahasa Indonesia (21654, 63016, 63015, 63027, 63112, 21608, 21211) + kode asli Twilio
- Frontend: kartu "Template WhatsApp (Twilio)" di Pengaturan → Notifikasi akun; alasan gagal yang jelas di Pengiriman terakhir
- Unit test: tests/test_whatsapp_content_template.py (dengan Twilio palsu)

## Backlog
- P1: Cek status persetujuan otomatis berkala + notifikasi kalau ditolak
- P2: Kirim ulang otomatis WhatsApp yang gagal setelah template disetujui
