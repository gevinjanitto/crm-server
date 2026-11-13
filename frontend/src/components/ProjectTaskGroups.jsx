import React from "react";
import { Link } from "react-router-dom";
import { FolderKanban } from "lucide-react";

export const groupByProject = (rows) => {
  const map = new Map();
  rows.forEach((t) => {
    if (!map.has(t.project_id)) map.set(t.project_id, { id: t.project_id, name: t.project_name, tasks: [] });
    map.get(t.project_id).tasks.push(t);
  });
  return [...map.values()];
};

export const ProjectTaskGroups = ({ rows, prefix, renderRow }) => groupByProject(rows).map((g) => (
  <li key={g.id} data-testid={`${prefix}-project-${g.id}`} style={{ marginTop: 10 }}>
    <Link to={`/projects/${g.id}/kanban`} data-testid={`${prefix}-project-link-${g.id}`}
      style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", color: "inherit", fontWeight: 600, fontSize: 13 }}>
      <FolderKanban size={14} />
      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{g.name}</span>
      <span className="note-badge" data-testid={`${prefix}-project-count-${g.id}`}>{g.tasks.length} task</span>
    </Link>
    <ul style={{ margin: 0, padding: "0 0 0 12px", listStyle: "none" }}>{g.tasks.map(renderRow)}</ul>
  </li>
));
