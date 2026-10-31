import React, { useState, useEffect } from "react";
import { Search, Pencil, ShieldCheck, Trash2, LoaderCircle } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { toast } from "sonner";
import { useAuth } from "../App";
import { api, useData, errorText, initials } from "../lib/api";
import {
  PageHead,
  Loading,
  ErrorState,
  Empty,
  AddButton,
  Badge,
  Modal,
  Field,
  SaveButton,
} from "../components/Common";
import { NotificationPausePanel, UserMuteToggles, ResetPasswordButton } from "../components/UserNotificationControls";
const roles = ["Admin", "Admin Project", "Developer", "Accounting", "Client"];
export default function Users() {
  const { user } = useAuth(),
    { data, loading, error, reload } = useData("/users"),
    [search, setSearch] = useState(""),
    [show, setShow] = useState(false),
    [editing, setEditing] = useState(null),
    [clients, setClients] = useState([]),
    [form, setForm] = useState({}),
    [busy, setBusy] = useState(false),
    [removing, setRemoving] = useState(null),
    [deleting, setDeleting] = useState(false),
    [formError, setFormError] = useState("");
  useEffect(() => {
    api
      .get("/clients")
      .then((r) => setClients(r.data))
      .catch(() => {});
  }, []);
  const open = (u) => {
    setEditing(u);
    setForm(
      u
        ? {
            name: u.name || "",
            username: u.username || "",
            email: u.email || "",
            whatsapp_number: u.whatsapp_number || "",
            role: u.role,
            client_id: u.client_id || "",
            active: u.active,
          }
        : {
            name: "",
            username: "",
            email: "",
            whatsapp_number: "",
            role: "Developer",
            client_id: "",
          },
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
        ? await api.patch(`/users/${editing.id}`, form)
        : await api.post("/users", form);
      toast.success(
        editing
          ? "User berhasil diperbarui"
          : "User dibuat dengan password awal 12345678. Notifikasi selamat datang dikirim ke in-app, email & WhatsApp.",
      );
      setShow(false);
      reload();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const toggle = async (u) => {
    try {
      await api.patch(`/users/${u.id}`, { active: !u.active });
      reload();
      toast.success(u.active ? "User dinonaktifkan" : "User diaktifkan");
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const remove = async () => {
    if (!removing) return;
    setDeleting(true);
    try {
      const { data: r } = await api.delete(`/users/${removing.id}`);
      toast.success(r.message || "User dihapus");
      setRemoving(null);
      reload();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setDeleting(false);
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data.filter((u) =>
    (u.name + " " + u.username + " " + (u.email || "") + " " + u.role)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHead
        eyebrow="WORKSPACE ACCESS"
        title="Manajemen user"
        description="Orang yang tepat, akses yang tepat."
      >
        <AddButton id="add-user" onClick={() => open(null)}>
          User baru
        </AddButton>
      </PageHead>
      <NotificationPausePanel />
      <div className="list-toolbar">
        <span className="tooltip-text" data-testid="users-count">
          {data.length} anggota workspace ·{" "}
          {data.filter((u) => u.active).length} aktif
        </span>
        <div className="list-search">
          <Search size={15} />
          <input
            data-testid="user-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari nama, username, email atau role..."
          />
        </div>
      </div>
      <div className="panel table-wrap">
        {rows.length ? (
          <table className="data-table" data-testid="users-table">
            <thead>
              <tr>
                <th>Nama</th>
                <th>Username</th>
                <th className="hide-mobile">Email</th>
                <th>Role</th>
                <th>Aktif</th>
                <th>Notif</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.id} data-testid={`user-row-${u.id}`}>
                  <td>
                    <div className="table-name">
                      <span className="avatar">{initials(u.name)}</span>
                      <div>
                        <b>{u.name}</b>
                        {u.id === user.id && <small>Anda</small>}
                      </div>
                    </div>
                  </td>
                  <td>{u.username}</td>
                  <td className="hide-mobile">{u.email}</td>
                  <td>
                    <Badge id={`user-role-${u.id}`}>{u.role}</Badge>
                  </td>
                  <td>
                    <input
                      data-testid={`user-active-${u.id}`}
                      type="checkbox"
                      checked={u.active}
                      onChange={() => toggle(u)}
                      disabled={u.id === user.id}
                      aria-label={`Status aktif ${u.name}`}
                    />
                  </td>
                  <td>
                    <UserMuteToggles user={u} onChanged={reload} />
                  </td>
                  <td>
                    <div className="row-actions user-row-actions">
                      <button
                        data-testid={`edit-user-${u.id}`}
                        className="icon-button"
                        title="Edit user"
                        aria-label={`Edit ${u.name}`}
                        onClick={() => open(u)}
                      >
                        <Pencil size={14} />
                      </button>
                      {u.id !== user.id && u.active && <ResetPasswordButton user={u} />}
                      {u.id !== user.id && (
                        <button
                          data-testid={`delete-user-${u.id}`}
                          className="icon-button danger user-delete-button"
                          title="Hapus user permanen"
                          aria-label={`Hapus ${u.name}`}
                          onClick={() => setRemoving(u)}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="User tidak ditemukan." />
        )}
      </div>
      <Modal
        open={show}
        onClose={() => setShow(false)}
        title={editing ? `Edit ${editing.name}` : "User baru"}
      >
        <form onSubmit={save}>
          <div className="form-grid user-form-grid">
            <Field
              label="Nama lengkap"
              name="name"
              value={form.name || ""}
              onChange={change}
              required
            />
            <Field
              label="Username"
              name="username"
              value={form.username || ""}
              onChange={change}
              minLength={3}
              pattern={editing ? "[a-zA-Z0-9_.@\-]+" : "[a-zA-Z0-9_.\-]+"}
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
              label="Nomor WhatsApp"
              name="whatsapp_number"
              type="tel"
              value={form.whatsapp_number || ""}
              onChange={change}
              placeholder="+628123456789"
            />
            <Field
              label="Role"
              name="role"
              as="select"
              options={roles}
              value={form.role || "Developer"}
              onChange={change}
            />
            {form.role === "Client" && (
              <Field
                label="Terhubung ke client"
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
            )}
          </div>
          {!editing && (
            <p className="form-note">
              Password awal otomatis <b>12345678</b> (sama seperti akun Client).
              Notifikasi selamat datang beserta username & password awal dikirim
              via in-app, email, dan WhatsApp (jika nomor diisi). Pengguna wajib
              mengganti password saat pertama kali login.
            </p>
          )}
          {formError && (
            <p className="form-error" data-testid="user-form-error">
              {formError}
            </p>
          )}
          <div className="form-actions">
            <SaveButton busy={busy} />
          </div>
        </form>
      </Modal>
      <AlertDialog
        open={Boolean(removing)}
        onOpenChange={(v) => !v && !deleting && setRemoving(null)}
      >
        <AlertDialogContent data-testid="delete-user-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Hapus user permanen?</AlertDialogTitle>
            <AlertDialogDescription>
              Akun <b>{removing?.name}</b> ({removing?.username}) akan dihapus
              permanen beserta sesi login dan notifikasinya. Tindakan ini tidak
              dapat dibatalkan. Gunakan centang “Aktif” jika hanya ingin
              menonaktifkan sementara.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-user-cancel" disabled={deleting}>
              Batal
            </AlertDialogCancel>
            <AlertDialogAction
              data-testid="delete-user-confirm"
              className="user-delete-confirm"
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault();
                remove();
              }}
            >
              {deleting && <LoaderCircle className="spin" size={15} />}
              {deleting ? "Menghapus..." : "Hapus permanen"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
