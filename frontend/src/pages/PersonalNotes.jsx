import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FileText, Search } from "lucide-react";
import { useData } from "../lib/api";
import { PageHead, Loading, ErrorState } from "../components/Common";
import { DocEditor } from "../components/workspace/DocsPage";
import { Action, DeleteAction, EmptyWorkspace, WorkspaceModal, FormField, Submit, useMutation } from "../components/workspace/WorkspaceUI";
import { useUnsavedGuard } from "../components/workspace/useUnsavedGuard";
import "../components/workspace/workspace.css";

const BASE = "/personal-notes";
const plain = (html) => String(html || "").replace(/<[^>]*>/g, " ");
const yearOf = (n) => String(n.created_at || "").slice(0, 4);

const Filters = ({ search, setSearch, year, setYear, years }) => (
  <div className="list-toolbar" data-testid="personal-notes-filters">
    <div className="toolbar-right">
      <div className="list-search">
        <Search size={15} />
        <input data-testid="personal-notes-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari judul atau isi notes..." />
      </div>
      <select className="filter-select" data-testid="personal-notes-year-filter" aria-label="Filter tahun notes dibuat" value={year} onChange={(e) => setYear(e.target.value)}>
        <option value="">Semua tahun</option>
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  </div>
);

const NoteList = ({ rows, current, saving, onOpen, onDelete }) => (
  <aside className="pw-doc-list" data-testid="personal-notes-list">
    {rows.map((d) => (
      <div key={d.id} className={d.id === current?.id ? "active" : ""}>
        <button data-testid={`open-personal-note-${d.id}`} aria-current={d.id === current?.id ? "page" : undefined} disabled={saving} onClick={() => onOpen(d)}>
          <FileText size={16} /><span>{d.title}<small>{new Date(d.updated_at).toLocaleDateString("id-ID")}</small></span>
        </button>
        {!saving && <DeleteAction id={`delete-personal-note-${d.id}`} onClick={() => onDelete(d)} />}
      </div>
    ))}
  </aside>
);

export default function PersonalNotes() {
  const docs = useData(BASE), [params, setParams] = useSearchParams(), [fresh, setFresh] = useState(null);
  const [creating, setCreating] = useState(false), [name, setName] = useState(""), [dirty, setDirty] = useState(false), [saving, setSaving] = useState(false);
  const [search, setSearch] = useState(""), [year, setYear] = useState("");
  const { run, busy } = useMutation();
  useUnsavedGuard(dirty || saving);
  const setSelected = (id) => setParams((prev) => { const next = new URLSearchParams(prev); if (id) next.set("doc", id); else next.delete("doc"); return next; }, { replace: true });
  if (docs.loading && !docs.data) return <Loading />;
  if (docs.error) return <ErrorState error={docs.error} reload={docs.reload} />;
  const all = docs.data || [], q = search.trim().toLowerCase();
  const years = [...new Set(all.map(yearOf).filter(Boolean))].sort((a, b) => b.localeCompare(a));
  const rows = all.filter((n) => (!year || yearOf(n) === year) && (!q || `${n.title} ${plain(n.content)}`.toLowerCase().includes(q)));
  const current = rows.find((d) => d.id === (fresh || params.get("doc"))) || rows[0];
  const canLeave = () => !saving && (!dirty || window.confirm("Perubahan belum disimpan. Tetap pindah notes?"));
  const open = (d) => { if (d.id !== current?.id && canLeave()) { setFresh(null); setSelected(d.id); setDirty(false); } };
  const remove = async (d) => { if (window.confirm("Hapus notes beserta riwayatnya?") && await run("delete", `${BASE}/${d.id}`)) { setDirty(false); setFresh(null); setSelected(null); await docs.reload(); } };
  const create = async (e) => {
    e.preventDefault();
    const d = await run("post", BASE, { title: name, content: "" }, "Notes dibuat");
    if (d) { setFresh(d.id); docs.setData([d, ...all]); setSelected(d.id); setDirty(false); setCreating(false); setSearch(""); setYear(""); }
  };
  return (
    <div data-testid="personal-notes-page">
      <PageHead eyebrow="NOTES PRIBADI" title="Notes Pribadi" description="Catatan pribadi akun Anda. Hanya Anda yang dapat melihatnya.">
        <Action id="create-personal-note" disabled={saving} onClick={() => { if (canLeave()) { setCreating(true); setName(""); } }}>Notes baru</Action>
      </PageHead>
      {all.length > 0 && <Filters {...{ search, setSearch, year, setYear, years }} />}
      <section className="panel panel-padding" data-testid="personal-notes-workspace">
        {!all.length ? <EmptyWorkspace title="Belum ada notes pribadi" id="personal-notes-empty" />
          : !rows.length ? <p className="form-note" data-testid="personal-notes-no-match">Tidak ada notes yang cocok dengan filter.</p>
          : <div className="pw-doc-layout">
              <NoteList rows={rows} current={current} saving={saving} onOpen={open} onDelete={remove} />
              {current && <DocEditor key={current.id} personal doc={current} base={BASE} editable onDirty={setDirty} onSaving={setSaving}
                onSaved={(d) => docs.setData((list) => list.map((r) => (r.id === d.id ? d : r)))} />}
            </div>}
      </section>
      <WorkspaceModal id="new-personal-note" open={creating} onClose={() => setCreating(false)} title="Notes baru">
        <form className="pw-form" onSubmit={create}>
          <FormField id="new-personal-note-title" label="Judul" required autoFocus maxLength={150} value={name} onChange={(e) => setName(e.target.value)} />
          <Submit id="new-personal-note-save" busy={busy}>Buat notes</Submit>
        </form>
      </WorkspaceModal>
    </div>
  );
}
