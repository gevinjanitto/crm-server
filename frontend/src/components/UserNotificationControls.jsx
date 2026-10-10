import React, { useEffect, useState } from "react";
import { Mail, MessageCircle, KeyRound, LoaderCircle, BellOff } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import { Switch } from "./ui/switch";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "./ui/alert-dialog";

const CHANNELS = [["email", "Email", Mail], ["whatsapp", "WhatsApp", MessageCircle]];

export const NotificationPausePanel = () => {
  const [pause, setPause] = useState(null);
  useEffect(() => { api.get("/admin/notification-pause").then((r) => setPause(r.data)).catch(() => {}); }, []);
  const change = async (key, value) => {
    const next = { ...pause, [key]: value };
    setPause(next);
    try {
      await api.put("/admin/notification-pause", next);
      toast.success(`Notifikasi ${key === "email" ? "email" : "WhatsApp"} semua akun ${value ? "dijeda" : "diaktifkan kembali"}`);
    } catch (e) { setPause(pause); toast.error(errorText(e)); }
  };
  if (!pause) return null;
  const any = pause.email || pause.whatsapp;
  return (
    <div className={`panel notif-pause-panel ${any ? "paused" : ""}`} data-testid="notification-pause-panel">
      <div className="notif-pause-text">
        <BellOff size={18} />
        <div>
          <b>Jeda notifikasi semua akun</b>
          <small>Saat dijeda, email/WhatsApp tidak dikirim ke akun mana pun. Notifikasi reset password tetap dikirim.</small>
        </div>
      </div>
      <div className="notif-pause-switches">
        {CHANNELS.map(([key, label, Icon]) => (
          <label key={key} className="notif-pause-switch">
            <Icon size={15} /> {label} {pause[key] ? "dijeda" : "aktif"}
            <Switch checked={pause[key]} onCheckedChange={(v) => change(key, v)} data-testid={`pause-all-${key}`} />
          </label>
        ))}
      </div>
    </div>
  );
};

export const UserMuteToggles = ({ user, onChanged }) => {
  const mute = user.notification_mute || {};
  const toggle = async (key) => {
    const next = { email: !!mute.email, whatsapp: !!mute.whatsapp, [key]: !mute[key] };
    try {
      await api.put(`/users/${user.id}/notification-mute`, next);
      toast.success(`${key === "email" ? "Email" : "WhatsApp"} ${user.name} ${next[key] ? "dijeda" : "diaktifkan"}`);
      onChanged();
    } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div className="user-mute-toggles">
      {CHANNELS.map(([key, label, Icon]) => (
        <button key={key} type="button" className={`user-mute ${mute[key] ? "muted" : ""}`} data-testid={`user-mute-${key}-${user.id}`}
          title={`${label}: ${mute[key] ? "dijeda (klik untuk aktifkan)" : "aktif (klik untuk jeda)"}`} onClick={() => toggle(key)}>
          <Icon size={13} />
        </button>
      ))}
    </div>
  );
};

export const ResetPasswordButton = ({ user }) => {
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/users/${user.id}/reset-password`);
      const via = data.channels.length ? data.channels.map((c) => (c === "email" ? "email" : "WhatsApp")).join(" & ") : null;
      toast.success(`${data.message} Password: ${data.default_password}.`, { description: via ? `Notifikasi terkirim via ${via}.` : "Email/WhatsApp belum terkirim, periksa kontak akun atau konfigurasi notifikasi." });
      setOpen(false);
    } catch (e) { toast.error(errorText(e)); }
    setBusy(false);
  };
  return (
    <>
      <button data-testid={`reset-password-${user.id}`} className="icon-button" title="Reset password ke default" aria-label={`Reset password ${user.name}`} onClick={() => setOpen(true)}>
        <KeyRound size={14} />
      </button>
      <AlertDialog open={open} onOpenChange={(v) => !v && !busy && setOpen(false)}>
        <AlertDialogContent data-testid="reset-password-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Reset password ke default?</AlertDialogTitle>
            <AlertDialogDescription>
              Password <b>{user.name}</b> ({user.username}) akan dikembalikan ke <b>12345678</b> dan semua sesi login akan keluar.
              Username & password dikirim ke email dan WhatsApp akun ini. Pengguna wajib membuat password baru saat login.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="reset-password-cancel" disabled={busy}>Batal</AlertDialogCancel>
            <AlertDialogAction data-testid="reset-password-confirm" disabled={busy} onClick={(e) => { e.preventDefault(); reset(); }}>
              {busy && <LoaderCircle className="spin" size={15} />}
              {busy ? "Mereset..." : "Reset password"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
