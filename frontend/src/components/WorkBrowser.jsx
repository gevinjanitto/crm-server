import React, { useMemo, useState } from "react";
import { Search, RotateCcw, Wrench, CheckCheck, Clock3, CalendarRange, X } from "lucide-react";
import { slug, useData } from "../lib/api";
import { WorkCards, WorkForm } from "./WorkComponents";
import { Loading, ErrorState, AddButton } from "./Common";

export const workYear = (r) => {
  const v = r.entry_date || r.created_at || "";
  return /^\d{4}/.test(v) ? v.slice(0, 4) : "";
};

/* Toolbar + daftar kartu yang sama untuk menu utama dan tab project (Revisi / Maintenance). */
export const WorkBrowser = ({ data, user, kind, reload, showProject = true, showStats = true }) => {
  const [search, setSearch] = useState(""),
    [project, setProject] = useState(""),
    [year, setYear] = useState(""),
    [filter, setFilter] = useState("Semua");
  const revision = kind === "revisions",
    statusTabs = revision
      ? ["Semua", "Terbuka", "Dikerjakan", "Selesai"]
      : ["Semua", "Belum dikerjakan", "Development", "Testing", "Selesai"];
  const projects = useMemo(() => [...new Map(data.map((r) => [r.project_id, r.project_name])).entries()], [data]);
  const years = useMemo(() => [...new Set(data.map(workYear).filter(Boolean))].sort((a, b) => b - a), [data]);
  const byYear = data.filter((r) => !year || workYear(r) === year),
    matching = byYear.filter(
      (r) =>
        `${r.title} ${r.project_name || ""}`.toLowerCase().includes(search.trim().toLowerCase()) &&
        (!project || r.project_id === project),
    ),
    rows = matching.filter((r) => filter === "Semua" || r.status === filter),
    hasFilters = Boolean(search || project || year || filter !== "Semua");
  const reset = () => { setSearch(""); setProject(""); setYear(""); setFilter("Semua"); };
  return (
    <>
      {showStats && (
        <div className="mini-stats">
          {[
            ["Total pekerjaan", byYear.length, revision ? RotateCcw : Wrench],
            ["Sedang aktif", byYear.filter((r) => r.status !== "Selesai").length, Clock3],
            ["Terselesaikan", byYear.filter((r) => r.status === "Selesai").length, CheckCheck],
          ].map(([n, v, Icon], i) => (
            <div className="mini-stat" key={n} data-testid={`work-stat-${i}`}>
              <Icon size={24} />
              <div><small>{n}</small><b>{v}</b></div>
            </div>
          ))}
        </div>
      )}
      <section className="work-toolbar" aria-label="Filter pekerjaan" data-testid="work-toolbar">
        <div className="work-status-tabs" role="group" aria-label="Status pekerjaan">
          {statusTabs.map((t) => (
            <button key={t} type="button" data-testid={`work-filter-${slug(t)}`}
              className={`work-status-tab ${filter === t ? "active" : ""}`} aria-pressed={filter === t} onClick={() => setFilter(t)}>
              {t}
              <span data-testid={`work-filter-count-${slug(t)}`}>{t === "Semua" ? matching.length : matching.filter((r) => r.status === t).length}</span>
            </button>
          ))}
        </div>
        <div className="work-toolbar-controls">
          <div className="work-project-control work-year-control">
            <CalendarRange size={15} aria-hidden="true" />
            <select className="filter-select" data-testid="work-year-filter" aria-label="Filter berdasarkan tahun" value={year} onChange={(e) => setYear(e.target.value)}>
              <option value="">Semua tahun</option>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          {showProject && (
            <div className="work-project-control">
              <select className="filter-select" data-testid="work-project-filter" aria-label="Filter berdasarkan project" value={project} onChange={(e) => setProject(e.target.value)}>
                <option value="">Semua project</option>
                {projects.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
              </select>
            </div>
          )}
          <div className="list-search work-search">
            <Search size={16} aria-hidden="true" />
            <input data-testid="work-search" aria-label="Cari pekerjaan" placeholder="Cari pekerjaan..." value={search} onChange={(e) => setSearch(e.target.value)} />
            {search && <button type="button" className="work-clear-search" data-testid="work-clear-search" aria-label="Hapus pencarian" onClick={() => setSearch("")}><X size={15} /></button>}
          </div>
          {hasFilters && <button type="button" className="work-reset" data-testid="work-reset-filters" onClick={reset}><RotateCcw size={14} />Reset filter</button>}
        </div>
      </section>
      <div className="work-results" data-testid="work-results" role="status" aria-live="polite">
        <span>Menampilkan <b>{rows.length}</b> dari {data.length} pekerjaan{year ? ` · tahun ${year}` : ""}</span>
        <span>{revision ? "Daftar revisi" : "Daftar maintenance"}</span>
      </div>
      <WorkCards rows={rows} user={user} kind={kind} reload={reload} filtered={hasFilters} showProject={showProject} />
    </>
  );
};

export const ProjectWorkTab = ({ p, user, kind }) => {
  const { data, loading, error, reload } = useData(`/projects/${p.id}/work/${kind}`),
    [show, setShow] = useState(false);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const manager = ["Admin", "Admin Project"].includes(user.role);
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>{kind === "revisions" ? "Revisi project" : "Maintenance project"}</h2>
        </div>
        {manager && (
          <AddButton id="add-project-work" onClick={() => setShow(true)}>
            Tambah {kind === "revisions" ? "revisi" : "maintenance"}
          </AddButton>
        )}
      </div>
      <WorkBrowser data={data} user={user} kind={kind} reload={reload} showProject={false} />
      <WorkForm open={show} onClose={() => setShow(false)} onSaved={reload} kind={kind} project={p} />
    </>
  );
};
