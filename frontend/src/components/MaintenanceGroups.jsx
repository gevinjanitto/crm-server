import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, FolderPlus, Pencil, Trash2, Wrench } from "lucide-react";
import { api, errorText } from "../lib/api";
import { Field } from "./Common";
import { WorkCards } from "./WorkComponents";

export const useMaintenanceGroups = (pid) => {
  const [groups, setGroups] = useState([]);
  const load = () => (pid ? api.get(`/projects/${pid}/maintenance-groups`).then((r) => setGroups(r.data)).catch(() => setGroups([])) : setGroups([]));
  useEffect(() => { load(); }, [pid]); // eslint-disable-line react-hooks/exhaustive-deps
  return [groups, load];
};

export const GroupSelect = ({ pid, value, onChange, testid = "maintenance-group-select", autoLabel = "Otomatis (Maintenance tahun berjalan)" }) => {
  const [groups, reload] = useMaintenanceGroups(pid);
  return (
    <div className="maint-group-select">
      <Field label="Grup maintenance" name="group_id" as="select" data-testid={testid}
        options={[{ value: "", label: groups.length ? autoLabel : "Otomatis: Maintenance tahun ini" }, ...groups.map((g) => ({ value: g.id, label: `${g.name} (${g.count} item)` }))]}
        value={value || ""} onChange={(e) => onChange(e.target.value)} />
      <button type="button" className="secondary-button maint-new-group" data-testid={`${testid}-create`}
        onClick={() => createGroup(pid, (g) => { reload(); onChange(g.id); })}>
        <FolderPlus size={15} /> Buat grup baru
      </button>
    </div>
  );
};

export const createGroup = async (pid, onDone) => {
  const name = window.prompt("Nama grup maintenance baru", `Maintenance ${new Date().getFullYear()}`);
  if (!name?.trim()) return;
  try { const r = await api.post(`/projects/${pid}/maintenance-groups`, { name }); toast.success("Grup maintenance dibuat"); onDone(r.data); }
  catch (e) { toast.error(errorText(e)); }
};

const GroupHeader = ({ g, open, toggle, manager, reload, showProject }) => {
  const rename = async () => {
    const name = window.prompt("Ubah nama grup maintenance", g.name);
    if (!name?.trim() || name === g.name) return;
    try { await api.patch(`/projects/${g.project_id}/maintenance-groups/${g.id}`, { name }); toast.success("Nama grup diperbarui"); reload(); }
    catch (e) { toast.error(errorText(e)); }
  };
  const remove = async () => {
    if (!window.confirm(`Hapus grup "${g.name}"?`)) return;
    try { await api.delete(`/projects/${g.project_id}/maintenance-groups/${g.id}`); toast.success("Grup dihapus"); reload(); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <h2 className="maint-group-heading">
      <button type="button" className="maint-group-toggle" data-testid={`maint-group-toggle-${g.key}`} aria-expanded={open} onClick={toggle}>
        <Wrench size={16} aria-hidden="true" />
        {showProject && g.project_name && <span className="maint-group-project-first" data-testid={`maint-group-project-${g.key}`}>{g.project_name}</span>}
        {showProject && g.project_name && <span className="maint-group-sep" aria-hidden="true">/</span>}
        <span className="maint-group-name" data-testid={`maint-group-name-${g.key}`}>{g.name}</span>
        <span className="maint-group-count" data-testid={`maint-group-count-${g.key}`}>{g.rows.length} item</span>
        <ChevronDown size={17} className={`maint-group-chevron ${open ? "" : "is-collapsed"}`} aria-hidden="true" />
      </button>
      {manager && g.id && <span className="maint-group-actions">
        <button type="button" className="icon-button" title="Ubah nama grup" data-testid={`maint-group-rename-${g.key}`} onClick={rename}><Pencil size={14} /></button>
        {!g.rows.length && <button type="button" className="icon-button danger" title="Hapus grup" data-testid={`maint-group-delete-${g.key}`} onClick={remove}><Trash2 size={14} /></button>}
      </span>}
    </h2>
  );
};

const buildGroups = (rows, extra) => {
  const map = new Map();
  extra.forEach((g) => map.set(g.id, { ...g, key: g.id, rows: [] }));
  rows.forEach((r) => {
    const key = r.group_id || `none-${r.project_id}`;
    if (!map.has(key)) map.set(key, { key, id: r.group_id, project_id: r.project_id, project_name: r.project_name, name: r.group_name || "Belum dikelompokkan (menunggu persetujuan)", year: r.group_year || "", rows: [] });
    const g = map.get(key);
    g.project_name = g.project_name || r.project_name;
    g.rows.push(r);
  });
  return [...map.values()].sort((a, b) => String(a.project_name || "").localeCompare(String(b.project_name || "")) || (b.id ? 1 : 0) - (a.id ? 1 : 0) || String(b.year).localeCompare(String(a.year)));
};

export const MaintenanceGroupList = ({ rows, user, reload, showProject, filtered, emptyGroups = [] }) => {
  const [open, setOpen] = useState({});
  const manager = ["Admin", "Admin Project"].includes(user.role);
  const groups = buildGroups(rows, filtered ? [] : emptyGroups);
  if (!groups.length) return <WorkCards rows={[]} user={user} kind="maintenances" reload={reload} filtered={filtered} showProject={showProject} />;
  return (
    <div className="maint-groups" data-testid="maintenance-groups">
      {groups.map((g) => {
        const isOpen = open[g.key] ?? false;
        return (
          <section className="maint-group" key={g.key} data-testid={`maint-group-${g.key}`}>
            <GroupHeader g={g} open={isOpen} manager={manager} reload={reload} showProject={showProject} toggle={() => setOpen((o) => ({ ...o, [g.key]: !isOpen }))} />
            {isOpen && (g.rows.length
              ? <WorkCards rows={g.rows} user={user} kind="maintenances" reload={reload} filtered={filtered} showProject={showProject} />
              : <p className="form-note" data-testid={`maint-group-empty-${g.key}`}>Belum ada maintenance di grup ini.</p>)}
          </section>
        );
      })}
    </div>
  );
};

export const NewGroupButton = ({ pid, onDone }) => (
  <button type="button" className="secondary-button maint-new-group" data-testid="maintenance-new-group" onClick={() => createGroup(pid, onDone)}>
    <FolderPlus size={15} /> Grup baru
  </button>
);
