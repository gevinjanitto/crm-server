import React, { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../App";
import "./legal.css";
import { api, errorText } from "../lib/api";
import "../components/assistant/assistant.css";

export const AFTER_LOGIN_KEY = "maiharta_after_login";

export default function OAuthAuthorize() {
  const { user, loading } = useAuth(), location = useLocation();
  const params = Object.fromEntries(new URLSearchParams(location.search));
  const [client, setClient] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!user) return;
    sessionStorage.removeItem(AFTER_LOGIN_KEY);
    api.get("/oauth/client", { params: { client_id: params.client_id, redirect_uri: params.redirect_uri } }).then((r) => setClient(r.data)).catch((e) => setError(errorText(e)));
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps
  if (loading) return null;
  if (!user) { sessionStorage.setItem(AFTER_LOGIN_KEY, location.pathname + location.search); return <Navigate to="/login" replace />; }
  const scopes = (params.scope || "read").split(/[\s,]+/);
  const decide = async (approve) => {
    setBusy(true);
    try {
      const r = await api.post("/oauth/approve", { client_id: params.client_id, redirect_uri: params.redirect_uri, code_challenge: params.code_challenge, code_challenge_method: params.code_challenge_method || "S256", state: params.state || "", scope: params.scope || "read", approve });
      window.location.href = r.data.redirect;
    } catch (e) { setError(errorText(e)); setBusy(false); }
  };
  return (
    <div className="oauth-page" data-testid="oauth-authorize-page">
      <div className="oauth-card">
        <ShieldCheck size={28} color="#c9963b" />
        <h1 data-testid="oauth-title">{client ? `Hubungkan ${client.client_name}` : "Otorisasi aplikasi"}</h1>
        {error ? <p className="form-error" data-testid="oauth-error">{error}</p> : client && (
          <>
            <p>Aplikasi <b>{client.client_name}</b> ({client.redirect_host}) meminta akses ke CRM Maiharta sebagai <b>{user.name}</b> ({user.role}).</p>
            <ul data-testid="oauth-scopes">
              <li>Membaca tugas, project, notes, dan maintenance yang bisa Anda akses</li>
              {scopes.includes("write") && <li>Melakukan aksi: assign, ubah status, subtask, komentar</li>}
            </ul>
            <p>Anda bisa mencabut akses kapan saja di Pengaturan → Token API.</p>
            <div className="oauth-actions">
              <button type="button" className="primary-button" disabled={busy} data-testid="oauth-approve-button" onClick={() => decide(true)}>Izinkan</button>
              <button type="button" className="secondary-button" disabled={busy} data-testid="oauth-deny-button" onClick={() => decide(false)}>Tolak</button>
            </div>
          </>
        )}
        <div className="legal-links"><Link to="/privacy" target="_blank">Kebijakan Privasi</Link><Link to="/terms" target="_blank">Ketentuan Layanan</Link><Link to="/support" target="_blank">Dukungan</Link></div>
      </div>
    </div>
  );
}
