import { ExpensesPanel } from "./Expenses";
import React, { useState, useEffect } from "react";
import { Plus, Trash2, Check, Clock, Code2 } from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText, money, dateLabel } from "../lib/api";
import {
  Loading,
  ErrorState,
  Empty,
  AddButton,
  Modal,
  Field,
  SaveButton,
  Badge,
} from "./Common";
export const FeaturesTab = ({ p, user, reloadProject }) => {
  const { data, loading, error, reload } = useData(
      `/projects/${p.id}/features`,
    ),
    [show, setShow] = useState(false),
    [team, setTeam] = useState([]),
    [form, setForm] = useState({
      name: "",
      category: "Frontend",
      price: 0,
      assigned_to: "",
      due_date: p.due_date,
    }),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState("");
  const manager = ["Admin", "Admin Project"].includes(user.role),
    canProgress = manager || user.role === "Developer";
  useEffect(() => {
    if (manager)
      api
        .get("/team")
        .then((r) =>
          setTeam(r.data.filter((t) => t.role !== 'Developer' || p.assigned_to.includes(t.id))),
        )
        .catch(() => {});
  }, [manager, p.assigned_to]);
  const change = (e) =>
    setForm({
      ...form,
      [e.target.name]:
        e.target.type === "number" ? Number(e.target.value) : e.target.value,
    });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/projects/${p.id}/features`, form);
      toast.success("Fitur ditambahkan");
      setShow(false);
      setForm({ ...form, name: "" });
      reload();
      reloadProject();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const progress = async (f, status) => {
    try {
      await api.patch(`/projects/${p.id}/features/${f.id}`, { status });
      reload();
      reloadProject();
      toast.success("Progress disimpan");
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const remove = async (f) => {
    if (!window.confirm(`Hapus fitur ${f.name}?`)) return;
    try {
      await api.delete(`/projects/${p.id}/features/${f.id}`);
      reload();
      reloadProject();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Breakdown fitur</h2>
          <p>
            {data.filter((f) => f.status === "Selesai").length} dari{" "}
            {data.length} fitur selesai
          </p>
        </div>
        {manager && (
          <AddButton
            id="add-feature"
            onClick={() => {
              setFormError("");
              setShow(true);
            }}
          >
            Tambah fitur
          </AddButton>
        )}
      </div>
      <div className="panel table-wrap">
        {data.length ? (
          <table className="data-table" data-testid="features-table">
            <thead>
              <tr>
                <th>Fitur</th>
                <th>Kategori</th>
                <th>Target</th>
                {manager && <th>Harga</th>}
                <th>Status</th>
                {manager && <th />}
              </tr>
            </thead>
            <tbody>
              {data.map((f) => (
                <tr key={f.id} data-testid={`feature-${f.id}`}>
                  <td>{f.name}</td>
                  <td>{f.category}</td>
                  <td>{dateLabel(f.due_date)}</td>
                  {manager && <td>{money(f.price)}</td>}
                  <td>
                    {canProgress ? (
                      <select
                        className="user-role-select"
                        data-testid={`feature-status-${f.id}`}
                        value={f.status}
                        onChange={(e) => progress(f, e.target.value)}
                      >
                        {["Belum dimulai", "Dikerjakan", "Selesai"].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    ) : (
                      <Badge id={`feature-badge-${f.id}`}>{f.status}</Badge>
                    )}
                  </td>
                  {manager && (
                    <td>
                      <button
                        data-testid={`delete-feature-${f.id}`}
                        className="icon-button danger"
                        onClick={() => remove(f)}
                        title="Hapus fitur"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="Belum ada fitur." />
        )}
      </div>
      <Modal open={show} onClose={() => setShow(false)} title="Tambah fitur">
        <form onSubmit={save}>
          <div className="form-grid">
            <div className="form-full">
              <Field
                label="Nama fitur"
                name="name"
                value={form.name}
                onChange={change}
                required
              />
            </div>
            <Field
              label="Kategori"
              name="category"
              as="select"
              options={["Frontend", "Backend", "UI/UX", "Lainnya"]}
              value={form.category}
              onChange={change}
            />
            <Field
              label="Harga fitur (Rp)"
              name="price"
              as="money"
              value={form.price}
              onChange={change}
            />
            <Field
              label="Penanggung jawab"
              name="assigned_to"
              as="select"
              options={[
                { value: "", label: "Belum ditugaskan" },
                ...team.map((t) => ({ value: t.id, label: t.name })),
              ]}
              value={form.assigned_to}
              onChange={change}
            />
            <Field
              label="Target selesai"
              name="due_date"
              type="date"
              value={form.due_date}
              onChange={change}
            />
          </div>
          {formError && (
            <p className="form-error" data-testid="feature-form-error">
              {formError}
            </p>
          )}
          <div className="form-actions">
            <SaveButton busy={busy} />
          </div>
        </form>
      </Modal>
    </>
  );
};
export const TimelineTab = ({ p }) => {
  const { data, loading, error, reload } = useData(
    `/projects/${p.id}/features`,
  );
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const duration = Math.max(1, new Date(p.due_date) - new Date(p.start_date));
  return (
    <section>
      <div className="section-heading">
        <div>
          <h2>Timeline project</h2>
          <p>
            {dateLabel(p.start_date)} — {dateLabel(p.due_date)}
          </p>
        </div>
        <Badge>{p.status}</Badge>
      </div>
      {data.map((f) => (
        <div
          className="timeline-item"
          key={f.id}
          data-testid={`timeline-feature-${f.id}`}
        >
          <span>{f.name}</span>
          <div className="timeline-bar">
            <span
              className={f.status === "Selesai" ? "done" : ""}
              style={{
                width: `${Math.min(100, Math.max(5, ((new Date(f.due_date || p.due_date) - new Date(p.start_date)) / duration) * 100))}%`,
              }}
            />
          </div>
          <span>{dateLabel(f.due_date)}</span>
        </div>
      ))}
      {!data.length && (
        <Empty message="Tambahkan fitur dan target tanggal untuk menyusun timeline." />
      )}
    </section>
  );
};
export const CostsTab = ({ p, user, reloadProject }) => {
  const { data, loading, error, reload } = useData(`/projects/${p.id}/costs`),
    [busy, setBusy] = useState(false),
    [form, setForm] = useState({
      development_cost: p.development_cost || 0,
      server_cost: p.server_cost || 0,
    });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/projects/${p.id}/costs`, form);
      toast.success("Biaya berhasil disimpan");
      reload();
      reloadProject();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <>
      <div className="finance-summary">
        {[
          ["Nilai project", data.value],
          ["Biaya development", data.development_cost],
          ["Biaya server", data.server_cost],
          ["Biaya lainnya", data.other_cost],
          ["Estimasi profit", data.profit],
        ].map(([n, v], i) => (
          <div
            className="finance-card"
            data-testid={`project-cost-${i}`}
            key={n}
          >
            <small>{n}</small>
            <b style={{ fontSize: 18 }}>{money(v)}</b>
          </div>
        ))}
      </div>
      <ExpensesPanel
        p={p}
        onChange={() => {
          reload();
          reloadProject();
        }}
      />
      {user.role === "Admin" && (
        <form onSubmit={save} style={{ maxWidth: 580, marginTop: 30 }}>
          <h2 className="detail-heading">Koreksi manual biaya internal</h2>
          <p className="form-note" style={{ marginBottom: 12 }}>
            Nilai ini otomatis terhitung dari pengeluaran di atas; ubah manual
            hanya jika diperlukan.
          </p>
          <div className="form-grid">
            <Field
              label="Biaya development (Rp)"
              name="development_cost"
              as="money"
              value={form.development_cost}
              onChange={(e) =>
                setForm({ ...form, development_cost: Number(e.target.value) })
              }
              required
            />
            <Field
              label="Biaya server (Rp)"
              name="server_cost"
              as="money"
              value={form.server_cost}
              onChange={(e) =>
                setForm({ ...form, server_cost: Number(e.target.value) })
              }
              required
            />
          </div>
          <div className="form-actions">
            <SaveButton busy={busy} />
          </div>
        </form>
      )}
    </>
  );
};
export const HistoryTab = ({ p }) => {
  const { data, loading, error, reload } = useData(`/projects/${p.id}/history`);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <section>
      <h2 className="detail-heading">Riwayat project</h2>
      {data.map((r) => (
        <div
          className="activity-item"
          key={r.id}
          data-testid={`history-${r.id}`}
        >
          <span className="activity-icon">
            <Clock size={13} />
          </span>
          <div>
            <b>{r.message}</b>
            <p>
              {r.user_name || "Tim MaiHarta"} ·{" "}
              {new Date(r.created_at).toLocaleString("id-ID")}
            </p>
            {r.note && <p>{r.note}</p>}
          </div>
        </div>
      ))}
      {!data.length && <Empty message="Belum ada riwayat." />}
    </section>
  );
};
