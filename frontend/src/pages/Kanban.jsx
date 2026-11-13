import React, { useEffect, useState } from "react";
import { useAuth } from "../App";
import { api, useData } from "../lib/api";
import { PageHead, Loading, ErrorState } from "../components/Common";
import { KanbanBoard } from "../components/KanbanBoard";
export default function Kanban() {
  const { user } = useAuth(),
    { data, loading, error, reload } = useData("/tasks"),
    { data: projects } = useData("/projects"),
    [team, setTeam] = useState([]),
    [project, setProject] = useState("");
  useEffect(() => {
    if (["Admin", "Admin Project"].includes(user.role))
      api
        .get("/team")
        .then((r) => setTeam(r.data))
        .catch(() => {});
  }, [user.role]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const teamFor = (t) => {
    const p = (projects || []).find((x) => x.id === t.project_id);
    return team.filter((d) => p?.assigned_to?.includes(d.id));
  };
  const rows = project ? data.filter((t) => t.project_id === project) : data;
  return (
    <>
      <PageHead
        eyebrow="WORKFLOW"
        title="Kanban"
        description="Semua task, subtask, dan status server dalam satu papan."
      >
        <select
          className="filter-select"
          data-testid="kanban-project-filter"
          value={project}
          onChange={(e) => setProject(e.target.value)}
        >
          <option value="">Semua project</option>
          {(projects || []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </PageHead>
      <KanbanBoard
        tasks={rows}
        user={user}
        reload={reload}
        teamFor={teamFor}
        showProject={!project}
        projectId={project || null}
      />
    </>
  );
}
