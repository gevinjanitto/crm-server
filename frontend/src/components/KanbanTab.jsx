import React, { useEffect, useState } from "react";
import { api, useData } from "../lib/api";
import { Loading, ErrorState } from "./Common";
import { KanbanBoard } from "./KanbanBoard";
export const KanbanTab = ({ p, user, dashboardOnly = false }) => {
  const tasks = useData(`/projects/${p.id}/tasks`),
    statuses = useData(`/projects/${p.id}/statuses`),
    workspace = useData(`/projects/${p.id}/workspace/meta`),
    [team, setTeam] = useState([]);
  useEffect(() => {
    if (["Admin", "Admin Project"].includes(user.role))
      api
        .get("/team")
        .then((r) => setTeam(r.data.filter((d) => d.role !== 'Developer' || p.assigned_to.includes(d.id))))
        .catch(() => {});
  }, [user.role, p]);
  if (tasks.loading || statuses.loading) return <Loading />;
  if (tasks.error || statuses.error)
    return (
      <ErrorState
        error={tasks.error || statuses.error}
        reload={() => {
          tasks.reload();
          statuses.reload();
        }}
      />
    );
  return (
    <KanbanBoard
      dashboardOnly={dashboardOnly}
      project={p}
      tasks={tasks.data}
      setTasks={tasks.setData}
      statuses={statuses.data}
      setStatuses={statuses.setData}
      user={user}
      team={team}
      workspace={workspace.data || { nodes: [], sprints: [], templates: [] }}
      reload={tasks.reload}
    />
  );
};
