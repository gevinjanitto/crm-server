import React, { useEffect, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import { Modal, Field, SaveButton } from "./Common";
import { Button } from "./ui/button";
const PLATFORMS = ["Web", "Mobile Android", "Mobile iOS", "Desktop", "UI/UX Design", "Lainnya"];
export const ProjectForm = ({ open, onClose, onSaved, project }) => {
  const [clients, setClients] = useState([]),
    [team, setTeam] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [files, setFiles] = useState([]);
  const [form, setForm] = useState({}),
    [newClient, setNewClient] = useState(null),
    [savingClient, setSavingClient] = useState(false);
  const saveClient = async () => {
    setSavingClient(true);
    setError("");
    try {
      const r = await api.post("/clients", newClient);
      setClients([r.data, ...clients]);
      setForm({ ...form, client_id: r.data.id });
      setNewClient(null);
      toast.success(
        r.data.account?.created
          ? `Client dibuat. Akun login: ${r.data.account.username} / ${r.data.account.password}`
          : "Client dibuat",
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSavingClient(false);
    }
  };
  useEffect(() => {
    if (!open) return;
    setError("");
    setFiles([]);
    setForm(
      project
        ? {
            ...Object.fromEntries(
              [
                "name",
                "client_id",
                "description",
                "type",
                "value",
                "start_date",
                "due_date",
                "assigned_to",
                "internal_notes",
              ].map((k) => [k, project[k] ?? ""]),
            ),
            platforms: project.platforms || [],
          }
        : {
            name: "",
            client_id: "",
            description: "",
            platforms: ["Web"],
            type: "Besar",
            value: 0,
            start_date: new Date().toISOString().slice(0, 10),
            due_date: new Date(Date.now() + 2592000000)
              .toISOString()
              .slice(0, 10),
            assigned_to: [],
            internal_notes: "",
          },
    );
    Promise.all([api.get("/clients"), api.get("/team")])
      .then(([c, t]) => {
        setClients(c.data);
        setTeam(t.data);
      })
      .catch((e) => setError(errorText(e)));
  }, [open, project]);
  const change = (e) =>
    setForm({
      ...form,
      [e.target.name]:
        e.target.type === "number" ? Number(e.target.value) : e.target.value,
    });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    if (!(form.platforms || []).length) {
      setError("Pilih minimal satu platform.");
      setBusy(false);
      return;
    }
    try {
      const r = project
        ? await api.patch(`/projects/${project.id}`, form)
        : await api.post("/projects", form);
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("kind", "Lampiran Project");
        fd.append("visibility", "Internal");
        await api
          .post(`/projects/${r.data.id}/documents`, fd)
          .catch((e) => toast.error(`${f.name}: ${errorText(e)}`));
      }
      toast.success(project ? "Project diperbarui" : "Project berhasil dibuat");
      onSaved(r.data);
      onClose();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={project ? "Edit project" : "Project baru"}
      description="Mulai langkah berikutnya bersama tim Anda."
    >
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="form-full">
            <Field
              label="Nama project"
              name="name"
              value={form.name || ""}
              onChange={change}
              placeholder="Contoh: Nusantara — Company Profile"
              required
            />
          </div>
          <div>
            <Field
              label="Client"
              name="client_id"
              as="select"
              options={[
                { value: "", label: "Pilih client" },
                ...clients.map((c) => ({ value: c.id, label: c.name })),
              ]}
              value={form.client_id || ""}
              onChange={change}
              required
            />
            {!project && !newClient && (
              <button
                type="button"
                className="link-button"
                data-testid="new-client-inline"
                style={{ marginTop: 6 }}
                onClick={() =>
                  setNewClient({ name: "", contact: "", email: "", phone: "" })
                }
              >
                + Client belum ada? Tambah di sini
              </button>
            )}
          </div>
          {newClient && (
            <div className="form-full inline-client" data-testid="inline-client">
              <div className="inline-client-head">
                <span>Client baru (akun login dibuat otomatis)</span>
                <button
                  type="button"
                  className="link-button"
                  data-testid="cancel-inline-client"
                  onClick={() => setNewClient(null)}
                >
                  Batal
                </button>
              </div>
              <div className="form-grid">
                <Field
                  label="Nama client"
                  name="nc_name"
                  value={newClient.name}
                  onChange={(e) =>
                    setNewClient({ ...newClient, name: e.target.value })
                  }
                />
                <Field
                  label="Nama kontak"
                  name="nc_contact"
                  value={newClient.contact}
                  onChange={(e) =>
                    setNewClient({ ...newClient, contact: e.target.value })
                  }
                />
                <Field
                  label="Email (jadi username)"
                  name="nc_email"
                  type="email"
                  value={newClient.email}
                  onChange={(e) =>
                    setNewClient({ ...newClient, email: e.target.value })
                  }
                />
                <Field
                  label="Telepon"
                  name="nc_phone"
                  value={newClient.phone}
                  onChange={(e) =>
                    setNewClient({ ...newClient, phone: e.target.value })
                  }
                />
              </div>
              <div className="form-actions">
                <Button
                  type="button"
                  className="secondary-button"
                  data-testid="save-inline-client"
                  disabled={
                    savingClient ||
                    !newClient.name ||
                    !newClient.contact ||
                    !newClient.email
                  }
                  onClick={saveClient}
                >
                  {savingClient ? "Menyimpan..." : "Simpan client"}
                </Button>
              </div>
            </div>
          )}
          <div className="form-full">
            <p className="form-note">
              Platform <em className="req-mark">*</em>{" "}
              <small className="opt-mark">(bisa lebih dari satu)</small>
            </p>
            <div className="platform-picker" data-testid="platform-picker">
              {PLATFORMS.map((pl) => {
                const on = (form.platforms || []).includes(pl);
                return (
                  <label key={pl} className={`platform-chip ${on ? "active" : ""}`}>
                    <input
                      type="checkbox"
                      data-testid={`platform-${pl.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                      checked={on}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          platforms: e.target.checked
                            ? [...(form.platforms || []), pl]
                            : form.platforms.filter((x) => x !== pl),
                        })
                      }
                    />
                    {pl}
                  </label>
                );
              })}
            </div>
          </div>
          <Field
            label="Skala project"
            name="type"
            as="select"
            options={["Besar", "Kecil"]}
            value={form.type || "Besar"}
            onChange={change}
            required
          />
          <Field
            label="Nilai project (Rp)"
            name="value"
            as="money"
            value={form.value ?? 0}
            onChange={change}
            required
          />
          <Field
            label="Tanggal mulai"
            name="start_date"
            type="date"
            value={form.start_date || ""}
            onChange={change}
            required
          />
          <Field
            label="Target selesai"
            name="due_date"
            type="date"
            min={form.start_date}
            value={form.due_date || ""}
            onChange={change}
            required
          />
          <div className="form-full">
            <Field
              label="Deskripsi"
              name="description"
              as="textarea"
              value={form.description || ""}
              onChange={change}
            />
          </div>
          <div className="form-full">
            <p className="form-note">
              Anggota tim yang ditugaskan{" "}
              <small className="opt-mark">(opsional)</small>
            </p>
            {team.map((t) => (
              <label key={t.id} className="checkbox-label">
                <input
                  data-testid={`assign-developer-${t.id}`}
                  type="checkbox"
                  checked={(form.assigned_to || []).includes(t.id)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      assigned_to: e.target.checked
                        ? [...(form.assigned_to || []), t.id]
                        : form.assigned_to.filter((id) => id !== t.id),
                    })
                  }
                />
                {t.name} · {t.role}
              </label>
            ))}
          </div>
          <div className="form-full">
            <Field
              label="Catatan internal"
              name="internal_notes"
              as="textarea"
              value={form.internal_notes || ""}
              onChange={change}
            />
          </div>
          {!project && (
            <div className="form-full">
              <Field
                label="Lampiran dokumen (bisa lebih dari satu, maks. 10 MB/file)"
                name="project_files"
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.txt,.csv,.png,.jpg,.jpeg,.webp"
                onChange={(e) => setFiles([...files, ...Array.from(e.target.files)])}
              />
              {files.length > 0 && (
                <ul className="file-list" data-testid="project-file-list">
                  {files.map((f, i) => (
                    <li key={i}>
                      <Paperclip size={14} /> {f.name}
                      <small>{(f.size / 1024).toFixed(0)} KB</small>
                      <button
                        type="button"
                        className="ck-icon danger"
                        onClick={() => setFiles(files.filter((_, j) => j !== i))}
                        aria-label="hapus file"
                      >
                        <X size={13} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
        <p className="form-legend">
          <em>*</em> wajib diisi
        </p>
        {error && (
          <p className="form-error" data-testid="project-form-error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button
            data-testid="cancel-project-form"
            type="button"
            variant="outline"
            onClick={onClose}
          >
            Batal
          </Button>
          <SaveButton
            busy={busy}
            label={project ? "Simpan perubahan" : "Buat project"}
          />
        </div>
      </form>
    </Modal>
  );
};
