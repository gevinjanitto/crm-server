import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, FileText, NotebookPen, ExternalLink, Search } from "lucide-react";
import { useData } from "../lib/api";
import { PageHead, Loading, ErrorState, Empty } from "../components/Common";

const groupByProject = (rows) => {
  const map = new Map();
  rows.forEach((r) => {
    if (!map.has(r.project_id)) map.set(r.project_id, { id: r.project_id, name: r.project_name, code: r.project_code, rows: [] });
    map.get(r.project_id).rows.push(r);
  });
  return [...map.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)));
};

const NoteCard = ({ n }) => {
  const navigate = useNavigate(), url = `/projects/${n.project_id}/docs?doc=${n.id}`;
  return (
  <article className="note-card is-clickable" data-testid={`note-card-${n.id}`} role="link" tabIndex={0} title="Buka notes di project"
    onClick={(e) => !e.target.closest("a") && navigate(url)} onKeyDown={(e) => e.key === "Enter" && navigate(url)}>
    <header className="note-card-head">
      <FileText size={15} aria-hidden="true" />
      <b data-testid={`note-title-${n.id}`} title={n.title}>{n.title}</b>
      <span className="note-badge">{n.visibility === "Client" ? "Tim & klien" : "Internal"}</span>
      <Link className="note-open" to={url} data-testid={`note-open-${n.id}`} title="Buka di project"><ExternalLink size={14} /></Link>
    </header>
    <small className="note-meta">{n.updated_by} · {new Date(n.updated_at).toLocaleString("id-ID")}{n.created_at && ` · Dibuat ${new Date(n.created_at).toLocaleDateString("id-ID")}`}</small>
    {n.content ? <div className="note-content" data-testid={`note-content-${n.id}`} dangerouslySetInnerHTML={{ __html: n.content.replace(/<input /g, '<input disabled tabindex="-1" ') }} />
      : <p className="form-note">Notes kosong.</p>}
  </article>
  );
};

const ProjectGroup = ({ g, open, toggle }) => (
  <section className="maint-group" data-testid={`notes-group-${g.id}`}>
    <h2 className="maint-group-heading">
      <button type="button" className="maint-group-toggle" data-testid={`notes-group-toggle-${g.id}`} aria-expanded={open} onClick={toggle}>
        <NotebookPen size={16} aria-hidden="true" />
        <span className="maint-group-project-first" data-testid={`notes-group-project-${g.id}`}>{g.name}</span>
        {g.code && <><span className="maint-group-sep" aria-hidden="true">/</span><span className="maint-group-name">{g.code}</span></>}
        <span className="maint-group-count" data-testid={`notes-group-count-${g.id}`}>{g.rows.length} notes</span>
        <ChevronDown size={17} className={`maint-group-chevron ${open ? "" : "is-collapsed"}`} aria-hidden="true" />
      </button>
    </h2>
    {open && <div className="notes-grid">{g.rows.map((n) => <NoteCard key={n.id} n={n} />)}</div>}
  </section>
);

const plain = (html) => String(html || "").replace(/<[^>]*>/g, " ");
const yearOf = (n) => String(n.created_at || "").slice(0, 4);

const NotesFilters = ({ search, setSearch, year, setYear, project, setProject, years, projects }) => (
  <div className="list-toolbar" data-testid="notes-filters">
    <div className="toolbar-right">
      <div className="list-search">
        <Search size={15} />
        <input data-testid="notes-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari judul atau isi notes..." />
      </div>
      <select className="filter-select" data-testid="notes-year-filter" aria-label="Filter tahun notes dibuat" value={year} onChange={(e) => setYear(e.target.value)}>
        <option value="">Semua tahun</option>
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
      <select className="filter-select" data-testid="notes-project-filter" aria-label="Filter project" value={project} onChange={(e) => setProject(e.target.value)}>
        <option value="">Semua project</option>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </div>
  </div>
);

export default function Notes() {
  const { data, loading, error, reload } = useData("/notes"), [open, setOpen] = useState({});
  const [search, setSearch] = useState(""), [year, setYear] = useState(""), [project, setProject] = useState("");
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data || [], q = search.trim().toLowerCase();
  const years = [...new Set(rows.map(yearOf).filter(Boolean))].sort((a, b) => b.localeCompare(a));
  const projects = groupByProject(rows);
  const filtered = rows.filter((n) => (!year || yearOf(n) === year) && (!project || n.project_id === project)
    && (!q || `${n.title} ${plain(n.content)}`.toLowerCase().includes(q)));
  const groups = groupByProject(filtered), filtering = Boolean(q || year || project);
  return (
    <div data-testid="notes-page">
      <PageHead eyebrow="PROJECT NOTES" title="Notes" description="Seluruh notes dari setiap project, dikelompokkan per project." />
      {rows.length > 0 && <NotesFilters {...{ search, setSearch, year, setYear, project, setProject, years, projects }} />}
      {!groups.length ? <Empty message={filtering ? "Tidak ada notes yang cocok dengan filter." : "Belum ada notes di project mana pun."} /> : (
        <div className="maint-groups" data-testid="notes-groups">
          {groups.map((g) => {
            const isOpen = open[g.id] ?? filtering;
            return <ProjectGroup key={g.id} g={g} open={isOpen} toggle={() => setOpen((o) => ({ ...o, [g.id]: !isOpen }))} />;
          })}
        </div>
      )}
    </div>
  );
}
