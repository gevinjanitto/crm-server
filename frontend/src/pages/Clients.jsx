import React, { useState } from "react";
import {
  Search,
  Mail,
  Phone,
  UserRound,
  ArrowUpRight,
  Pencil,
  Trash2,
  Building2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "../App";
import { useData, api, errorText, initials } from "../lib/api";
import {
  PageHead,
  AddButton,
  Loading,
  ErrorState,
  Empty,
  Modal,
  Field,
  SaveButton,
} from "../components/Common";
export default function Clients() {
  const { user } = useAuth(),
    { data, loading, error, reload } = useData("/clients"),
    [search, setSearch] = useState(""),
    [show, setShow] = useState(false),
    [editing, setEditing] = useState(null),
    [form, setForm] = useState({}),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState("");
  const canEdit = ["Admin", "Admin Project"].includes(user.role);
  const open = (c) => {
    setEditing(c);
    setForm(
      c
        ? Object.fromEntries(
            ["name", "contact", "email", "phone", "industry", "address"].map(
              (k) => [k, c[k] || ""],
            ),
          )
        : {
            name: "",
            contact: "",
            email: "",
            phone: "",
            industry: "",
            address: "",
          },
    );
    setFormError("");
    setShow(true);
  };
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = editing
        ? await api.patch(`/clients/${editing.id}`, form)
        : await api.post("/clients", form);
      toast.success(
        r.data.account?.created
          ? `Client disimpan. Akun login: ${r.data.account.username} / ${r.data.account.password}`
          : "Client berhasil disimpan",
        { duration: 8000 },
      );
      setShow(false);
      reload();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const remove = async (c) => {
    if (!window.confirm(`Hapus client ${c.name}?`)) return;
    try {
      await api.delete(`/clients/${c.id}`);
      toast.success("Client dihapus");
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data.filter((c) =>
    (c.name + " " + c.contact + " " + c.email)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHead
        eyebrow="RELATIONSHIP MANAGEMENT"
        title="Client"
        description="Hubungan yang baik, awal dari kolaborasi yang hebat."
      >
        {canEdit && (
          <AddButton id="add-client" onClick={() => open(null)}>
            Client baru
          </AddButton>
        )}
      </PageHead>
      <div className="list-toolbar">
        <span className="tooltip-text" data-testid="clients-count">
          {rows.length} client terdaftar
        </span>
        <div className="list-search">
          <Search size={15} />
          <input
            data-testid="client-search"
            placeholder="Cari client..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      <div className="client-grid">
        {rows.map((c, i) => (
          <article
            className="client-card"
            key={c.id}
            data-testid={`client-card-${c.id}`}
          >
            <div className="client-card-head">
              <span className={`client-monogram glyph-${i % 4}`}>
                {initials(c.name)}
              </span>
              {canEdit && (
                <div className="row-actions">
                  <button
                    className="icon-button"
                    data-testid={`edit-client-${c.id}`}
                    title="Edit client"
                    onClick={() => open(c)}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    className="icon-button danger"
                    data-testid={`delete-client-${c.id}`}
                    title="Hapus client"
                    onClick={() => remove(c)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              )}
            </div>
            <h2>{c.name}</h2>
            <p>{c.industry || "—"}</p>
            <div className="client-contact">
              <div>
                <UserRound size={13} />
                {c.contact}
              </div>
              <div>
                <Mail size={13} />
                {c.email}
              </div>
              <div>
                <Phone size={13} />
                {c.phone || "—"}
              </div>
            </div>
            <div className="client-card-footer">
              <span>
                <b>{c.project_count}</b> project
              </span>
              <Link
                to={`/projects?q=${encodeURIComponent(c.name)}`}
                className="section-link"
                data-testid={`client-projects-${c.id}`}
              >
                Lihat project <ArrowUpRight size={13} />
              </Link>
            </div>
          </article>
        ))}
      </div>
      {!rows.length && <Empty message="Belum ada client yang sesuai." />}
      <Modal
        open={show}
        onClose={() => setShow(false)}
        title={editing ? "Edit client" : "Client baru"}
      >
        <form onSubmit={submit}>
          <div className="form-grid">
            <div className="form-full">
              <Field
                label="Nama perusahaan / client"
                name="name"
                value={form.name || ""}
                onChange={change}
                required
              />
            </div>
            <Field
              label="Nama kontak"
              name="contact"
              value={form.contact || ""}
              onChange={change}
              required
            />
            <Field
              label="Email"
              name="email"
              type="email"
              value={form.email || ""}
              onChange={change}
              required
            />
            <Field
              label="Telepon"
              name="phone"
              value={form.phone || ""}
              onChange={change}
            />
            <Field
              label="Industri"
              name="industry"
              value={form.industry || ""}
              onChange={change}
            />
            <div className="form-full">
              <Field
                label="Alamat"
                name="address"
                as="textarea"
                value={form.address || ""}
                onChange={change}
              />
            </div>
          </div>
          {formError && (
            <p className="form-error" data-testid="client-form-error">
              {formError}
            </p>
          )}
          {!editing && (
            <p className="hint-text" data-testid="client-account-hint">
              Akun login client dibuat otomatis: username = email, password
              default <b>12345678</b> (wajib diganti saat login pertama).
            </p>
          )}
          <div className="form-actions">
            <SaveButton busy={busy} />
          </div>
        </form>
      </Modal>
    </>
  );
}
