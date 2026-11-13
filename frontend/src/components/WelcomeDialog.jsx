import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { FolderKanban, Bell, KeyRound, ArrowRight, Sparkles } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "./ui/dialog";
import { useAuth } from "../App";
import { api } from "../lib/api";
import "./welcome-dialog.css";

const tips = [
  [FolderKanban, "Pantau project", "Lihat status, progres, dan tim setiap project di satu tempat."],
  [Bell, "Notifikasi real-time", "Atur notifikasi in-app, email, dan WhatsApp di menu Pengaturan."],
  [KeyRound, "Jaga keamanan akun", "Password awal sudah Anda ganti. Simpan password baru dengan aman."],
];

export default function WelcomeDialog() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [closing, setClosing] = useState(false);
  const open = Boolean(user?.welcome_pending && !user?.must_change_password);
  const dismiss = async (goSettings = false) => {
    if (closing) return;
    setClosing(true);
    try { await api.post("/auth/welcome-seen"); } catch { /* popup stays dismissed for this session */ }
    setUser((current) => (current ? { ...current, welcome_pending: false } : current));
    setClosing(false);
    if (goSettings) navigate("/settings");
  };
  if (!user) return null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && dismiss()}>
      <DialogContent className="welcome-dialog" data-testid="welcome-dialog">
        <div className="welcome-hero">
          <motion.img
            src="/assets/logo-mark-white.png"
            alt="MaiHarta"
            className="welcome-logo"
            initial={{ scale: 0.6, opacity: 0, rotate: -12 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 16, delay: 0.1 }}
          />
          <span className="welcome-chip"><Sparkles size={13} /> Akun baru aktif</span>
        </div>
        <div className="welcome-body">
          <DialogTitle className="welcome-title" data-testid="welcome-title">
            Selamat datang di CRM Maiharta, {user.name.split(" ")[0]}!
          </DialogTitle>
          <DialogDescription className="welcome-desc">
            Akun Anda sudah siap dengan role <b>{user.role}</b>. Berikut beberapa hal untuk memulai.
          </DialogDescription>
          <ul className="welcome-tips">
            {tips.map(([Icon, title, text], i) => (
              <motion.li
                key={title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.08 }}
              >
                <span className="welcome-tip-icon"><Icon size={17} /></span>
                <div><b>{title}</b><small>{text}</small></div>
              </motion.li>
            ))}
          </ul>
          <div className="welcome-actions">
            <button type="button" className="welcome-secondary" data-testid="welcome-settings" disabled={closing} onClick={() => dismiss(true)}>
              Atur notifikasi
            </button>
            <button type="button" className="primary-button welcome-primary" data-testid="welcome-start" disabled={closing} onClick={() => dismiss()}>
              Mulai bekerja <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
