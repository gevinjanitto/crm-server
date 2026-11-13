import React, { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText } from "../lib/api";
import {
  Loading,
  ErrorState,
  AddButton,
  Modal,
  Field,
  SaveButton,
  Badge,
} from "./Common";
const groups = ["Development", "Server", "Lainnya"];
export const CostTypesPanel = () => {
  const { data, loading, error, reload } = useData("/cost-types"),
    [editing, setEditing] = useState(null),
    [show, setShow] = useState(false),
    [form, setForm] = useState({}),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState("");
  const open = (c) => {
    setEditing(c);
    setForm(
      c
        ? { name: c.name, group: c.group, description: c.description || "" }
        : { name: "", group: "Lainnya", description: "" },
    );
    setFormError("");
    setShow(true);
  };
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      editing
        ? await api.patch(`/cost-types/${editing.id}`, form)
        : await api.post("/cost-types", form);
      toast.success("Jenis biaya disimpan");
      setShow(false);
      reload();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const toggle = async (c) => {
    try {
      await api.patch(`/cost-types/${c.id}`, { active: !c.active });
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const remove = async (c) => {
    if (!window.confirm(`Hapus jenis biaya ${c.name}?`)) return;
    try {
      await api.delete(`/cost-types/${c.id}`);
      toast.success("Jenis biaya dihapus");
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <div className="panel panel-padding" style={{ marginBottom: 27 }}>
      <div className="section-heading">
        <div>
          <h2>Master jenis biaya</h2>
          <p>Kategori pengeluaran yang dipakai saat mencatat biaya project</p>
        </div>
        <AddButton id="add-cost-type" onClick={() => open(null)}>
          Jenis biaya
        </AddButton>
      </div>
      <div className="table-wrap">
        <table className="data-table" data-testid="cost-types-table">
          <thead>
            <tr>
              <th>Nama</th>
              <th>Kelompok</th>
              <th className="hide-mobile">Keterangan</th>
              <th>Dipakai</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr key={c.id} data-testid={`cost-type-row-${c.id}`}>
                <td>
                  <b>{c.name}</b>
                </td>
                <td>
                  <Badge>{c.group}</Badge>
                </td>
                <td className="hide-mobile">{c.description || "—"}</td>
                <td>{c.usage}x</td>
                <td>
                  <button
                    className={`status-badge ${c.active ? "green" : "neutral"}`}
                    style={{ border: 0, cursor: "pointer" }}
                    data-testid={`toggle-cost-type-${c.id}`}
                    onClick={() => toggle(c)}
                  >
                    <i />
                    {c.active ? "Aktif" : "Nonaktif"}
                  </button>
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      data-testid={`edit-cost-type-${c.id}`}
                      title="Edit"
                      onClick={() => open(c)}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="icon-button danger"
                      data-testid={`delete-cost-type-${c.id}`}
                      title="Hapus"
                      onClick={() => remove(c)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal
        open={show}
        onClose={() => setShow(false)}
        title={editing ? "Edit jenis biaya" : "Jenis biaya baru"}
      >
        <form onSubmit={save}>
          <div className="form-grid">
            <Field
              label="Nama jenis biaya"
              name="name"
              value={form.name || ""}
              onChange={change}
              required
            />
            <Field
              label="Kelompok"
              name="group"
              as="select"
              options={groups}
              value={form.group || "Lainnya"}
              onChange={change}
            />
            <div className="form-full">
              <Field
                label="Keterangan"
                name="description"
                as="textarea"
                value={form.description || ""}
                onChange={change}
              />
            </div>
          </div>
          {formError && (
            <p className="form-error" data-testid="cost-type-form-error">
              {formError}
            </p>
          )}
          <div className="form-actions">
            <SaveButton busy={busy} />
          </div>
        </form>
      </Modal>
    </div>
  );
};
