import React, { useState } from "react";
import { RotateCcw, Trash2, Search } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../App";
import { api, useData, errorText } from "../lib/api";
import { PageHead, Loading, ErrorState, Empty } from "../components/Common";

const TYPES = ["", "project", "task", "fitur", "revisi", "maintenance", "dokumen"];

export default function Trash() {
  const { user } = useAuth(),
    { data, loading, error, reload } = useData("/trash"),
    [type, setType] = useState(""),
    [q, setQ] = useState("");
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data.filter(
    (r) =>
      (!type || r.entity_type === type) &&
      (r.name + " " + r.deleted_by_name).toLowerCase().includes(q.toLowerCase()),
  );
  const restore = async (r) => {
    try {
      const res = await api.post(`/trash/${r.id}/restore`);
      toast.success(res.data.message);
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const purge = async (r) => {
    if (!window.confirm(`Hapus permanen "${r.name}"? Tindakan ini tidak dapat dibatalkan.`)) return;
    try {
      await api.delete(`/trash/${r.id}`);
      toast.success("Dihapus permanen");
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <>
      <PageHead
        eyebrow="ARSIP"
        title="Recycle Bin"
        description="Item yang dihapus tersimpan di sini dan dapat dipulihkan kapan saja."
      />
      <div className="list-toolbar">
        <div className="filter-tabs">
          {TYPES.map((t) => (
            <button
              key={t || "semua"}
              data-testid={`trash-filter-${t || "semua"}`}
              className={`filter-tab ${type === t ? "active" : ""}`}
              onClick={() => setType(t)}
            >
              {t ? t[0].toUpperCase() + t.slice(1) : "Semua"}
              <span>{t ? data.filter((r) => r.entity_type === t).length : data.length}</span>
            </button>
          ))}
        </div>
        <div className="list-search">
          <Search size={15} />
          <input data-testid="trash-search" placeholder="Cari item..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      <div className="panel table-wrap">
        {rows.length ? (
          <table className="data-table" data-testid="trash-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Jenis</th>
                <th>Dihapus oleh</th>
                <th>Waktu</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} data-testid={`trash-row-${r.id}`}>
                  <td>
                    <b>{r.name || "(tanpa nama)"}</b>
                  </td>
                  <td>
                    <span className="sample-tag">{r.entity_type}</span>
                  </td>
                  <td>{r.deleted_by_name}</td>
                  <td>{new Date(r.deleted_at).toLocaleString("id-ID")}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="ck-primary" data-testid={`restore-${r.id}`} onClick={() => restore(r)} style={{ padding: "6px 10px" }}>
                      <RotateCcw size={14} /> Pulihkan
                    </button>{" "}
                    {user.role === "Admin" && (
                      <button className="ck-danger" data-testid={`purge-${r.id}`} onClick={() => purge(r)} style={{ padding: "6px 10px" }}>
                        <Trash2 size={14} /> Permanen
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="Arsip kosong." />
        )}
      </div>
    </>
  );
}
