import React from "react";
import { toast } from "sonner";
import { api, useData, errorText } from "../../lib/api";
import { TokenRow, deleteToken, useTokensSync } from "./ApiTokens";

export const AdminTokens = () => {
  const { data, reload } = useData("/admin/tokens");
  useTokensSync(reload);
  const revoke = async (t) => {
    if (!window.confirm(`Cabut token "${t.name}" milik ${t.user_name}?`)) return;
    try { await api.delete(`/admin/tokens/${t.id}`); toast.success("Token dicabut"); reload(); window.dispatchEvent(new Event("tokens-changed")); } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div data-testid="admin-tokens">
      <h3 style={{ marginTop: 18, fontSize: 14 }}>Semua token & koneksi ({data?.length || 0})</h3>
      <div className="ai-token-list">
        {(data || []).map((t) => <TokenRow key={t.id} t={t} owner={t.user_name} onRevoke={revoke} onDelete={(x) => deleteToken(x, `/admin/tokens/${x.id}/purge`, reload)} prefix="admin" />)}
        {data?.length === 0 && <p className="form-note">Belum ada token.</p>}
      </div>
    </div>
  );
};
