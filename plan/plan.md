# Perbaikan Pengiriman WhatsApp via Twilio — CRM Server

Clone proyek `gevinjanitto/crm-server`, lalu perbaiki error "Twilio menolak pesan (HTTP 400, kode 21654): ContentSid Required".
Template pesan yang sudah ada di aplikasi dikirim ke Twilio sebagai Content Template resmi, lalu WhatsApp dikirim memakai template tersebut.

## Penyebab error (ringkas)
Twilio menolak pesan karena permintaan berisi nilai variabel template (ContentVariables) tetapi tidak menyertakan kode template Twilio (ContentSid, diawali "HX"). Template di aplikasi belum terdaftar di Twilio, jadi kode HX itu memang belum ada. Untuk WhatsApp bisnis, pesan di luar jendela 24 jam juga wajib memakai template yang sudah disetujui WhatsApp.

## Untuk siapa
Pemilik/admin CRM yang mengirim WhatsApp ke kontak lewat aplikasi ini.

## Fitur inti dan pengalaman
- Template WhatsApp yang sudah ada di aplikasi (isi, nama, variabel) tetap sama, tidak diubah.
- Tiap template disalin ke Twilio sebagai Content Template dan diajukan untuk persetujuan WhatsApp; kode HX disimpan bersama template di aplikasi.
- Status persetujuan tiap template terlihat (menunggu / disetujui / ditolak).
- Pengiriman WhatsApp memakai kode HX + nilai variabel, sesuai format yang diminta Twilio.
- Pesan gagal di "Pengiriman terakhir" ditampilkan dengan penjelasan bahasa Indonesia yang mudah dipahami (misalnya "Template belum terdaftar/disetujui di Twilio"), kode asli Twilio tetap terlihat kecil di bawahnya.
- Bagian lain aplikasi (email, kontak, tampilan lain) tidak diubah.

## Alur pengguna
1. Admin membuka daftar template WhatsApp yang sudah ada.
2. Admin menekan "Sinkronkan ke Twilio" → template terdaftar di Twilio dan diajukan ke WhatsApp.
3. Setelah status "Disetujui", pengiriman WhatsApp berjalan seperti biasa.
4. Jika gagal, admin melihat alasan yang jelas dan langkah perbaikannya.

## Nuansa UI/UX
Mengikuti tampilan aplikasi saat ini apa adanya; hanya menambah tombol sinkronisasi, label status template, dan teks error yang lebih jelas dengan gaya yang sama.

## Tahap implementasi
- **Tahap 1 (dikerjakan sekarang):** clone proyek, temukan kode pengiriman WhatsApp, daftarkan template aplikasi ke Twilio, kirim memakai kode HX, tampilkan status template dan pesan error yang jelas.
- **Tahap 2:** pembaruan status persetujuan otomatis berkala dan notifikasi jika template ditolak.
- **Tahap 3:** pengiriman ulang otomatis untuk pesan yang gagal setelah template disetujui.

## Asumsi
- Kredensial Twilio (Account SID, Auth Token, nomor pengirim WhatsApp) sudah ada di proyek; jika belum ada di lingkungan ini, akan diminta lewat kartu aman.
- Semua template WhatsApp yang ada di aplikasi diajukan dengan kategori "Utility" (notifikasi transaksional); bahasa template Indonesia.
- Placeholder di template aplikasi diubah otomatis ke format Twilio ({{1}}, {{2}}, …) hanya di sisi Twilio; teks di aplikasi tetap sama.
- Persetujuan WhatsApp dilakukan oleh Meta dan bisa memakan waktu menit hingga 1–2 hari; selama menunggu, pesan ke kontak di luar jendela 24 jam tetap akan gagal (dengan penjelasan yang jelas).
- Tidak ada perubahan pada fitur email maupun bagian lain aplikasi.
- Jika struktur repo ternyata berbeda dari dugaan (misalnya template tidak tersimpan di aplikasi), rencana disesuaikan dengan cara paling dekat tanpa mengubah fitur lain.
