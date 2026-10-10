import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { useAuth } from "../App";
import { useData, download, statuses } from "../lib/api";
import { PageHead, AddButton, Loading, ErrorState, ExportButton } from "../components/Common";
import { ProjectYearGroups } from "../components/ProjectYearGroups";
import { projectStartYear } from "../lib/projectYears";
import { ProjectForm } from "../components/ProjectForm";
export default function Projects() {
  const { user } = useAuth(),
    { data, loading, error, reload } = useData("/projects"),
    [params] = useSearchParams(),
    navigate = useNavigate();
  const [search, setSearch] = useState(params.get("q") || ""),
    [tab, setTab] = useState(params.get("tab") || "Semua project"),
    [filter, setFilter] = useState(""),
    [year, setYear] = useState(""),
    [show, setShow] = useState(false);
  useEffect(() => setSearch(params.get("q") || ""), [params]);
  useEffect(() => setTab(params.get("tab") || "Semua project"), [params]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const years = [...new Set(data.map(projectStartYear))].sort((a, b) =>
    a === "undated" ? 1 : b === "undated" ? -1 : Number(b) - Number(a),
  );
  const rows = data.filter(
      (p) =>
        (p.name + " " + p.client_name + " " + p.code)
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (!filter || p.status === filter) &&
        (!year || projectStartYear(p) === year) &&
        (tab === "Semua project" ||
          (tab === "Aktif" ? p.status !== "Selesai" : p.status === "Selesai")),
    );
  return (
    <>
      <PageHead
        eyebrow="PROJECT MANAGEMENT"
        title="Semua project"
        description={`${data.length} project, berbagai ide hebat. Satu ruang kolaborasi.`}
      >
        <ExportButton
          testid="export-projects"
          onExport={() =>
            download("/reports/projects.xlsx", "laporan-project-maiharta.xlsx")
          }
        >
          Ekspor
        </ExportButton>
        {["Admin", "Admin Project"].includes(user.role) && (
          <AddButton id="add-project" onClick={() => setShow(true)}>
            Project baru
          </AddButton>
        )}
      </PageHead>
      <div className="list-toolbar">
        <div className="filter-tabs">
          {["Semua project", "Aktif", "Selesai"].map((t) => (
            <button
              key={t}
              data-testid={`projects-tab-${t.replace(" ", "-").toLowerCase()}`}
              className={`filter-tab ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
            >
              {t}
              <span>
                {t === "Semua project"
                  ? data.length
                  : data.filter((p) =>
                      t === "Aktif"
                        ? p.status !== "Selesai"
                        : p.status === "Selesai",
                    ).length}
              </span>
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <div className="list-search">
            <Search size={15} />
            <input
              data-testid="project-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nama atau client..."
            />
          </div>
          <select
            className="filter-select"
            data-testid="project-year-filter"
            aria-label="Filter berdasarkan tahun"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          >
            <option value="">Semua tahun</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y === "undated" ? "Belum ada tanggal mulai" : y}
              </option>
            ))}
          </select>
          <select
            className="filter-select"
            data-testid="project-status-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">Semua status</option>
            {statuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>
      <p className="project-groups-summary" data-testid="projects-count">{rows.length} dari {data.length} project{year ? ` · tahun ${year === "undated" ? "belum ada tanggal mulai" : year}` : ""}</p>
      <ProjectYearGroups projects={rows} filterKey={`${search}\u0000${tab}\u0000${filter}\u0000${year}`} />
      <ProjectForm
        open={show}
        onClose={() => setShow(false)}
        onSaved={(p) => navigate(`/projects/${p.id}`)}
      />
    </>
  );
}
