import React from "react";
import { Link, useLocation } from "react-router-dom";
import { ShieldCheck, FileText, LifeBuoy } from "lucide-react";
import "./legal.css";

const EMAIL = process.env.REACT_APP_CONTACT_EMAIL || "cvmaiharta@gmail.com";
const UPDATED = "Juni 2026";

const PAGES = {
  privacy: {
    icon: ShieldCheck, title: "Kebijakan Privasi", sections: [
      ["Siapa kami", "CRM Maiharta adalah aplikasi internal CV MaiHarta untuk mengelola proyek, tugas (Kanban), notes, dan maintenance. Kebijakan ini juga berlaku untuk integrasi AI: Asisten AI, server MCP, dan koneksi ChatGPT/Claude."],
      ["Data yang kami proses", "Data akun (nama, username, email, role), data kerja (project, tugas, subtask, komentar, notes, maintenance), serta log aktivitas (audit trail) termasuk aksi yang dilakukan melalui AI. Untuk token API & OAuth kami hanya menyimpan hash token, nama, scope, waktu dibuat, dan waktu terakhir dipakai."],
      ["Data yang dibagikan ke aplikasi AI", "Saat Anda menghubungkan ChatGPT, Claude, atau klien MCP lain, aplikasi tersebut hanya dapat membaca data yang memang boleh Anda akses sesuai role Anda, dan hanya melakukan aksi tulis (assign, ubah status, subtask, komentar) bila token/izin memiliki scope write. Data yang dikirim ke penyedia AI tunduk pada kebijakan privasi penyedia tersebut (OpenAI, Anthropic, atau penyedia OpenAI-compatible yang dikonfigurasi admin)."],
      ["Yang tidak kami lakukan", "Kami tidak menjual data, tidak memakai data untuk iklan, dan tidak membagikan password. Token hanya ditampilkan sekali dan tidak pernah dicatat dalam log."],
      ["Penyimpanan & keamanan", "Data disimpan di server milik CV MaiHarta dengan akses terbatas dan koneksi HTTPS. Token yang dicabut langsung ditolak. Admin dapat menonaktifkan seluruh fitur AI kapan saja."],
      ["Hak Anda", `Anda dapat mencabut akses aplikasi AI kapan saja di Pengaturan → Token API & koneksi AI, serta meminta salinan atau penghapusan data pribadi dengan menghubungi ${EMAIL}.`],
    ],
  },
  terms: {
    icon: FileText, title: "Ketentuan Layanan", sections: [
      ["Penerimaan", "Dengan memakai CRM Maiharta, termasuk koneksi melalui ChatGPT, Claude, atau klien MCP, Anda menyetujui ketentuan ini."],
      ["Akun & akses", "Akun diberikan oleh admin CV MaiHarta untuk tim internal dan klien. Anda bertanggung jawab menjaga kerahasiaan password dan token API. Jangan bagikan token kepada pihak lain."],
      ["Penggunaan AI", "Asisten AI dan integrasi MCP membantu membaca dan mengelola tugas. Hasil AI bisa keliru; periksa kembali sebelum mengambil keputusan penting. Setiap aksi yang dilakukan AI atas nama Anda tercatat di audit trail dan menjadi tanggung jawab pemilik akun."],
      ["Larangan", "Dilarang memakai layanan untuk mengakses data di luar hak akses Anda, mengganggu sistem, melewati pembatasan (rate limit), atau menyalahgunakan token."],
      ["Ketersediaan", "Layanan disediakan apa adanya. Fitur AI dapat dinonaktifkan atau diubah sewaktu-waktu oleh admin. Kami dapat mencabut akses yang melanggar ketentuan."],
      ["Kontak", `Pertanyaan mengenai ketentuan ini: ${EMAIL}.`],
    ],
  },
  support: {
    icon: LifeBuoy, title: "Dukungan", sections: [
      ["Hubungi kami", `Email: ${EMAIL}. Kami membalas pada hari kerja (Senin–Jumat, 09.00–17.00 WITA).`],
      ["Menghubungkan ChatGPT", "Di ChatGPT, tambahkan connector dengan URL server MCP (https://<domain>/api/mcp) dan autentikasi OAuth. Login ke CRM pada halaman persetujuan lalu klik Izinkan."],
      ["Menghubungkan Claude / Cursor", "Buat token di Pengaturan → Token API & koneksi AI, lalu pakai header Authorization: Bearer mh_pat_... pada URL server MCP."],
      ["Mencabut akses", "Buka Pengaturan → Token API & koneksi AI lalu klik Cabut pada token atau koneksi OAuth. Akses langsung terputus."],
      ["Masalah umum", "401: token salah/dicabut/kedaluwarsa — buat token baru atau hubungkan ulang. 403 \"dinonaktifkan\": fitur AI dimatikan admin. 403 \"read-only\": token tidak memiliki scope write. 429: terlalu banyak permintaan, tunggu satu menit."],
    ],
  },
};

export default function LegalPage({ kind }) {
  const page = PAGES[kind], Icon = page.icon, { pathname } = useLocation();
  return (
    <div className="legal-page" data-testid={`legal-page-${kind}`}>
      <nav className="legal-nav">
        <b>CRM Maiharta</b>
        {[["privacy", "Privasi"], ["terms", "Ketentuan"], ["support", "Dukungan"]].map(([k, l]) => (
          <Link key={k} to={`/${k}`} className={pathname === `/${k}` ? "active" : ""} data-testid={`legal-nav-${k}`}>{l}</Link>
        ))}
      </nav>
      <article className="legal-card">
        <Icon size={28} className="legal-icon" />
        <h1 data-testid="legal-title">{page.title}</h1>
        <p className="legal-meta">CV MaiHarta · Terakhir diperbarui {UPDATED}</p>
        {page.sections.map(([h, t]) => <section key={h}><h2>{h}</h2><p>{t}</p></section>)}
        <p className="legal-contact">Kontak: <a href={`mailto:${EMAIL}`} data-testid="legal-contact-email">{EMAIL}</a></p>
      </article>
    </div>
  );
}
