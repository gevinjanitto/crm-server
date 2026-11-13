import React, { useState } from "react";
import { Search } from "lucide-react";
import { useData } from "../lib/api";
import { PageHead, Loading, ErrorState, Empty } from "../components/Common";

const TYPES = ["", "project", "task", "fitur", "revisi", "maintenance", "dokumen", "tiket", "status kanban", "user", "client", "sesi"];
const slug = (s) => s.toLowerCase().replace(/\s+/g, "-");

export default function Audit() {
  const [type, setType] = useState(""),
    [q, setQ] = useState("");
  const { data, loading, error, reload } = useData(
    `/audit?limit=500${type ? `&entity_type=${encodeURIComponent(type)}` : ""}`,
  );
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data.filter((r) =>
    (r.name + " " + r.user_name + " " + r.action + " " + r.entity_type).toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <>
      <PageHead
        eyebrow="KEAMANAN"
        title="Audit Trail"
        description="Jejak lengkap siapa melakukan apa, kapan, dan pada data yang mana."
      />
      <div className="list-toolbar">
        <div className="filter-tabs" style={{ flexWrap: "wrap" }}>
          {TYPES.map((t) => (
            <button
              key={t || "semua"}
              data-testid={`audit-filter-${t ? slug(t) : "semua"}`}
              className={`filter-tab ${type === t ? "active" : ""}`}
              onClick={() => setType(t)}
            >
              {t ? t[0].toUpperCase() + t.slice(1) : "Semua"}
            </button>
          ))}
        </div>
        <div className="list-search">
          <Search size={15} />
          <input data-testid="audit-search" placeholder="Cari user / item / aksi..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      <div className="panel table-wrap">
        {rows.length ? (
          <table className="data-table audit-table" data-testid="audit-table">
            <thead>
              <tr>
                <th>Waktu</th>
                <th>User</th>
                <th>Aksi</th>
                <th>Jenis</th>
                <th>Item</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} data-testid={`audit-row-${r.id}`}>
                  <td style={{ whiteSpace: "nowrap" }}>{new Date(r.created_at).toLocaleString("id-ID")}</td>
                  <td>
                    <b>{r.user_name}</b>
                    <br />
                    <small style={{ color: "#6b7690" }}>{r.user_role}</small>
                  </td>
                  <td>
                    <span className={`audit-action ${slug(r.action)}`}>{r.action}</span>
                  </td>
                  <td>{r.entity_type}</td>
                  <td>{r.name || <small style={{ color: "#98a2b8" }}>{r.entity_id}</small>}</td>
                  <td>
                    {r.details && Object.keys(r.details).length > 0 && (
                      <span className="audit-details">
                        {Object.entries(r.details)
                          .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
                          .join("\n")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="Belum ada aktivitas tercatat." />
        )}
      </div>
    </>
  );
}
