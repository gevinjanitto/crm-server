import React, { useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, LockKeyhole } from "lucide-react";
import { useAuth } from "../App";
import { api, errorText, initials } from "../lib/api";
import { PageHead, Field, SaveButton, Badge } from "../components/Common";
import { NotificationSettings } from '../components/NotificationSettings';
export default function Settings() {
  const { user, logout } = useAuth(),
    [form, setForm] = useState({
      current_password: "",
      new_password: "",
      confirm: "",
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setError("");
    if (form.new_password !== form.confirm) {
      setError("Konfirmasi password belum sesuai.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/password", {
        current_password: form.current_password,
        new_password: form.new_password,
      });
      toast.success("Password berhasil diubah. Silakan masuk kembali.");
      await logout();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHead
        eyebrow="PREFERENSI"
        title="Pengaturan"
        description="Ruang kerja Anda, kenyamanan Anda."
      />
      {user.must_change_password && (
        <div className="force-password" data-testid="force-password-banner">
          Ini login pertama Anda. Demi keamanan, silakan ganti password default
          sebelum melanjutkan ke menu lain.
        </div>
      )}
      <div className="settings-layout" data-testid="settings-layout">
        <NotificationSettings />
        <div className="settings-account-column" data-testid="settings-account-column">
        <section className="panel panel-padding settings-profile" data-testid="settings-profile">
          <div className="section-heading">
            <h2>Profil akun</h2>
            <ShieldCheck size={18} color="#7d9de2" />
          </div>
          <div className="profile-summary">
            <span className="avatar">{initials(user.name)}</span>
            <div>
              <h2 data-testid="profile-name">{user.name}</h2>
              <p data-testid="profile-email">{user.email}</p>
            </div>
          </div>
          <div
            className="detail-summary no-margin"
            style={{ borderBottom: 0, paddingBottom: 0 }}
          >
            <div>
              <small>Username</small>
              <b data-testid="profile-username">{user.username}</b>
            </div>
            <div>
              <small>Role</small>
              <Badge id="profile-role">{user.role}</Badge>
            </div>
            <div>
              <small>Status akun</small>
              <Badge id="profile-status">Aktif</Badge>
            </div>
          </div>
        </section>
        <section className="panel panel-padding settings-security" data-testid="settings-security">
          <div className="section-heading">
            <div>
              <h2>Keamanan akun</h2>
              <p>Perbarui password secara berkala untuk menjaga akun Anda.</p>
            </div>
            <LockKeyhole size={18} color="#7d9de2" />
          </div>
          <form onSubmit={save}>
            <div className="form-grid">
              <div className="form-full">
                <Field
                  label="Password saat ini"
                  name="current_password"
                  type="password"
                  autoComplete="current-password"
                  value={form.current_password}
                  onChange={change}
                  required
                />
              </div>
              <Field
                label="Password baru"
                name="new_password"
                type="password"
                autoComplete="new-password"
                minLength={10}
                value={form.new_password}
                onChange={change}
                required
              />
              <Field
                label="Konfirmasi password baru"
                name="confirm"
                type="password"
                autoComplete="new-password"
                minLength={10}
                value={form.confirm}
                onChange={change}
                required
              />
            </div>
            {error && (
              <p className="form-error" data-testid="password-error">
                {error}
              </p>
            )}
            <div className="form-actions">
              <SaveButton busy={busy} label="Ubah password" />
            </div>
          </form>
        </section>
        </div>
      </div>
    </>
  );
}
