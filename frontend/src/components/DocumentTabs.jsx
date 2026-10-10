import React, { useState } from "react";
import {
  FileText,
  Download,
  Trash2,
  Check,
  Circle,
  Server,
  ArrowUpRight,
} from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText, dateLabel, download } from "../lib/api";
import { DocPreview, PreviewButton } from "./DocPreview";
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
const kinds = [
  "Kontrak",
  "Requirement",
  "Rincian Fitur",
  "Timeline",
  "UI/UX Design",
  "Penawaran Harga",
  "Invoice",
  "Akses Server",
  "BAST",
  "Dokumentasi Penggunaan",
];
export const DocumentsTab = ({ p, user }) => {
  const { data, loading, error, reload } = useData(
      `/projects/${p.id}/documents`,
    ),
    [show, setShow] = useState(false),
    [file, setFile] = useState(null),
    [name, setName] = useState(''),
    [url, setUrl] = useState(''),
    [source, setSource] = useState('file'),
    [kind, setKind] = useState("Requirement"),
    [visibility, setVisibility] = useState("Internal"),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState(""),
    [preview, setPreview] = useState(null);
  const manager = ["Admin", "Admin Project"].includes(user.role);
  const save = async (e) => {
    e.preventDefault();
    if (source === 'file' && !file) return;
    setBusy(true);
    setFormError("");
    const f = new FormData();
    if (source === 'file') f.append("file", file);
    else f.append('url', url);
    f.append('name', name);
    f.append("kind", kind);
    f.append("visibility", visibility);
    try {
      await api.post(`/projects/${p.id}/documents`, f);
      toast.success("Dokumen berhasil ditambahkan");
      setShow(false);
      setFile(null);
      setName(''); setUrl('');
      reload();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const remove = async (d) => {
    if (!window.confirm(`Hapus dokumen ${d.name}?`)) return;
    try {
      await api.delete(`/projects/${p.id}/documents/${d.id}`);
      toast.success("Dokumen dihapus");
      reload();
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
          <h2>Dokumen project</h2>
          <p>{data.length} dokumen tersimpan</p>
        </div>
        {manager && (
          <AddButton
            id="upload-document"
            onClick={() => {
              setFormError("");
              setShow(true);
            }}
          >
            Tambah dokumen
          </AddButton>
        )}
      </div>
      {manager && (
        <div className="required-docs">
          {kinds.slice(0, 4).map((k) => {
            const complete = data.some((d) => d.kind === k);
            return (
              <span
                data-testid={`required-doc-${k.replace(" ", "-")}`}
                key={k}
                className={complete ? "complete" : ""}
              >
                {complete ? <Check size={12} /> : <Circle size={11} />} {k}
              </span>
            );
          })}
        </div>
      )}
      <div className="document-grid">
        {data.map((d) => (
          <article
            className="document-card"
            key={d.id}
            data-testid={`document-${d.id}`}
          >
            <FileText size={27} />
            <h3 data-testid={`document-name-${d.id}`} style={{overflowWrap:'anywhere'}}>{d.name}</h3>
            <p>
              {d.kind} · {d.document_type === 'link' ? 'Link' : `${(d.size / 1024).toFixed(1)} KB`}
            </p>
            <p style={{ marginTop: 7 }}>
              {dateLabel(d.created_at)} · {d.visibility}
            </p>
            <div className="document-card-bottom">
              <span className="tooltip-text">{d.uploaded_by}</span>
              <div className="row-actions">
                {d.document_type === 'link' ? <a className="icon-button" title="Buka link dokumen" data-testid={`open-document-link-${d.id}`} href={d.url} target="_blank" rel="noopener noreferrer"><ArrowUpRight size={15}/></a> : <><PreviewButton testid={`preview-document-${d.id}`} onClick={() => setPreview({ name: d.filename || d.name, path: `/projects/${p.id}/documents/${d.id}/download`, type: d.content_type })} /><button
                  className="icon-button"
                  title="Unduh dokumen"
                  data-testid={`download-document-${d.id}`}
                  onClick={() =>
                    download(
                      `/projects/${p.id}/documents/${d.id}/download`,
                      d.filename || d.name,
                    )
                  }
                >
                  <Download size={15} />
                </button></>}
                {manager && (
                  <button
                    className="icon-button danger"
                    title="Hapus dokumen"
                    data-testid={`delete-document-${d.id}`}
                    onClick={() => remove(d)}
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
      {!data.length && <Empty message="Belum ada dokumen project." />}
      <DocPreview file={preview} onClose={() => setPreview(null)} />
      <Modal open={show} onClose={() => setShow(false)} title="Tambah dokumen">
        <form onSubmit={save}>
          <div className="form-grid">
            <div className="form-full"><Field label="Nama dokumen" name="document_name" value={name} maxLength={200} onChange={e => setName(e.target.value)} required /></div>
            <div className="form-full"><Field label="Sumber dokumen" name="document_source" as="select" options={[{value:'file',label:'File'},{value:'link',label:'Link'}]} value={source} onChange={e => setSource(e.target.value)} /></div>
            <Field
              label="Jenis dokumen"
              name="kind"
              as="select"
              options={kinds}
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            />
            <Field
              label="Akses dokumen"
              name="visibility"
              as="select"
              options={["Internal", "Client"]}
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
            />
            <div className="form-full">
              {source === 'link' ? <Field label="Link dokumen" name="document_url" type="url" placeholder="https://docs.google.com/..." value={url} onChange={e => setUrl(e.target.value)} required /> : <Field
                label="Pilih file (maks. 10 MB)"
                name="file"
                type="file"
                accept=".pdf,.docx,.xlsx,.txt,.csv,.png,.jpg,.jpeg,.webp"
                required
                onChange={(e) => setFile(e.target.files[0])}
              />}
            </div>
          </div>
          {formError && (
            <p className="form-error" data-testid="document-form-error">
              {formError}
            </p>
          )}
          <div className="form-actions">
            <SaveButton busy={busy} label="Simpan dokumen" />
          </div>
        </form>
      </Modal>
    </>
  );
};
export const DeploymentsTab = ({ p, user }) => {
  const { data, loading, error, reload } = useData(
      `/projects/${p.id}/deployments`,
    ),
    [show, setShow] = useState(false),
    [busy, setBusy] = useState(false),
    [formError, setFormError] = useState(""),
    [form, setForm] = useState({
      environment: "Development",
      url: "",
      version: "",
      notes: "",
    });
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/projects/${p.id}/deployments`, form);
      toast.success("Deployment dicatat");
      setShow(false);
      reload();
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Tracking deployment</h2>
          <p>Riwayat rilis development dan production</p>
        </div>
        <AddButton
          id="add-deployment"
          onClick={() => {
            setFormError("");
            setShow(true);
          }}
        >
          Catat deployment
        </AddButton>
      </div>
      {data.map((d) => (
        <div
          className="deployment-item"
          data-testid={`deployment-${d.id}`}
          key={d.id}
        >
          <span className="project-glyph">
            <Server size={19} />
          </span>
          <div>
            <Badge>{d.environment}</Badge>
            <h3>{d.version}</h3>
            <a
              href={d.url}
              target="_blank"
              rel="noreferrer"
              data-testid={`deployment-url-${d.id}`}
            >
              {d.url} ↗
            </a>
            <p>{d.notes}</p>
          </div>
          <span className="tooltip-text">
            {dateLabel(d.created_at)}
            <br />
            {d.created_by}
          </span>
        </div>
      ))}
      {!data.length && <Empty message="Belum ada deployment tercatat." />}
      <Modal
        open={show}
        onClose={() => setShow(false)}
        title="Catat deployment"
      >
        <form onSubmit={save}>
          <div className="form-grid">
            <Field
              label="Environment"
              name="environment"
              as="select"
              options={
                user.role === "Admin" && p.production_at
                  ? ["Development", "Production"]
                  : ["Development"]
              }
              value={form.environment}
              onChange={change}
            />
            <Field
              label="Versi / tag rilis"
              name="version"
              placeholder="v1.0.0"
              value={form.version}
              onChange={change}
              required
            />
            <div className="form-full">
              <Field
                label="URL server"
                name="url"
                type="url"
                placeholder="https://..."
                value={form.url}
                onChange={change}
                required
              />
            </div>
            <div className="form-full">
              <Field
                label="Catatan rilis"
                name="notes"
                as="textarea"
                value={form.notes}
                onChange={change}
              />
            </div>
          </div>
          {formError && (
            <p className="form-error" data-testid="deployment-form-error">
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
