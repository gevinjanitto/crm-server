import React, { useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Pencil, Check, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../App";
import {
  api,
  useData,
  errorText,
  dateLabel,
  statuses,
  money,
} from "../lib/api";
import {
  PageHead,
  Loading,
  ErrorState,
  Badge,
  Progress,
} from "../components/Common";
import { Button } from "../components/ui/button";
import { ProjectForm } from "../components/ProjectForm";
import {
  CostsTab,
  HistoryTab,
} from "../components/ProjectTabs";
import { DocumentsTab, DeploymentsTab } from "../components/DocumentTabs";
import { ProjectWorkTab } from "../components/WorkBrowser";
import { KanbanTab } from "../components/KanbanTab";
import { WorkspacePage } from "../components/workspace/WorkspacePage";
import { ProjectNavigation, workspaceTabs, visibleWorkspaceTabs } from "../components/workspace/ProjectNavigation";
import "../components/workspace/workspace.css";
import Tickets from './Tickets';
import { useProjectTicketSummary } from '../hooks/useProjectTicketSummary';
import { canListProjects } from '../lib/projectAccess';
import { StatusPicker, canChangeAnyStatus } from '../components/StatusPicker';
export default function ProjectDetail() {
  const { id, section } = useParams(),
    { user } = useAuth(),
    navigate = useNavigate(),
    { data: p, loading, error, reload } = useData(`/projects/${id}`),
    [edit, setEdit] = useState(false);
  const { data: ticketSummary, mutate: refreshTicketSummary } = useProjectTicketSummary(id, user.role);
  const previousSection = useRef(section);
  useEffect(() => {
    if (previousSection.current !== section) {
      previousSection.current = section;
      reload();
    }
  }, [section, reload]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const manager = ["Admin", "Admin Project"].includes(user.role),
    internal = ["Admin", "Admin Project", "Developer"].includes(user.role);
  const tabs = [
    "Ringkasan",
    "Kanban",
    "Dokumen",
    ...(["Admin", "Accounting"].includes(user.role) ? ["Keuangan"] : []),
    ...(internal ? ["Deployment", "Revisi", "Maintenance"] : []),
    ...(['Admin', 'Admin Project', 'Developer', 'Client'].includes(user.role) ? ['Tiket'] : []),
    "Riwayat",
  ];
  const advanced = workspaceTabs.some(([key]) => key === section);
  const tab = advanced || section === 'dashboard' ? '' : tabs.find(t => t.toLowerCase() === section) || 'Ringkasan';
  if (section && section !== 'dashboard' && !tabs.some(t => t.toLowerCase() === section) && !visibleWorkspaceTabs(user.role).some(([key]) => key === section)) {
    return <Navigate to={`/projects/${id}/ringkasan`} replace />;
  }
  const remove = async () => {
    if (!window.confirm("Hapus project baru ini?")) return;
    try {
      await api.delete(`/projects/${id}`);
      toast.success("Project dihapus");
      navigate("/projects");
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <>
      <Link className="back-link" to={canListProjects(user) ? '/projects' : '/'} data-testid={canListProjects(user) ? 'back-to-projects' : 'back-to-dashboard'}>
        <ArrowLeft size={14} />
        {canListProjects(user) ? 'Semua project' : 'Dashboard'}
      </Link>
      <PageHead
        eyebrow={`${p.code} / ${(p.platforms || [p.category]).join(" · ")}`}
        title={p.name}
        description={p.client_name}
      >
        <Badge id="detail-project-status">{p.status}</Badge>
        {manager && (
          <Button
            className="secondary-button"
            data-testid="edit-project"
            onClick={() => setEdit(true)}
          >
            <Pencil size={14} />
            Edit project
          </Button>
        )}
        {manager && p.status === "Project Masuk" && (
          <button
            className="icon-button danger"
            title="Hapus project"
            data-testid="delete-project"
            onClick={remove}
          >
            <Trash2 size={16} />
          </button>
        )}
      </PageHead>
      {!advanced && <div className="detail-summary">
        <div data-testid="detail-client">
          <small>Client</small>
          <b>{p.client_name}</b>
        </div>
        <div data-testid="detail-start">
          <small>Tanggal mulai</small>
          <b>{dateLabel(p.start_date)}</b>
        </div>
        <div data-testid="detail-deadline">
          <small>Target selesai</small>
          <b>{dateLabel(p.due_date)}</b>
        </div>
        <div>
          <small>Progress keseluruhan</small>
          <Progress id="detail-progress" value={p.progress} />
        </div>
      </div>}
      <ProjectNavigation id={id} section={section} tabs={tabs} tab={tab} role={user.role} ticketSummary={ticketSummary} />
      <div className="detail-content" key={section || tab}>
        {advanced && <WorkspacePage p={p} user={user} section={section} />}
        {section === 'dashboard' && <KanbanTab p={p} user={user} dashboardOnly />}
        {section !== 'dashboard' && tab === "Ringkasan" && <Overview p={p} user={user} reload={reload} />}{" "}
        {tab === "Kanban" && <KanbanTab p={p} user={user} />}{" "}
        {tab === 'Tiket' && <Tickets key={id} project={p} onTicketsChanged={refreshTicketSummary} />}
        {tab === "Dokumen" && <DocumentsTab p={p} user={user} />}{" "}
        {tab === "Keuangan" && (
          <CostsTab p={p} user={user} reloadProject={reload} />
        )}{" "}
        {tab === "Deployment" && <DeploymentsTab p={p} user={user} />}{" "}
        {tab === "Revisi" && (
          <ProjectWorkTab p={p} user={user} kind="revisions" />
        )}{" "}
        {tab === "Maintenance" && (
          <ProjectWorkTab p={p} user={user} kind="maintenances" />
        )}{" "}
        {tab === "Riwayat" && <HistoryTab p={p} />}
      </div>
      <ProjectForm
        open={edit}
        onClose={() => setEdit(false)}
        project={p}
        onSaved={reload}
      />
    </>
  );
}
const Overview = ({ p, user, reload }) => {
  const idx = statuses.indexOf(p.status),
    canChange = canChangeAnyStatus(user.role, p.status, statuses);
  return (
    <div className="detail-overview">
      <section>
        <h2 className="detail-heading">Tentang project</h2>
        <p className="detail-description" data-testid="project-description">
          {p.description || "Belum ada deskripsi."}
        </p>
        <div className="overview-stats">
          <div data-testid="project-scale">
            <small>Skala project</small>
            <b>{p.type}</b>
          </div>
          <div data-testid="project-developer-count">
            <small>Anggota tim</small>
            <b>{p.assigned_to.length}</b>
          </div>
          {p.value !== undefined && (
            <div data-testid="project-value">
              <small>Nilai project</small>
              <b style={{ fontSize: 15 }}>{money(p.value)}</b>
            </div>
          )}
        </div>
        {p.internal_notes && (
          <div className="note-block" data-testid="project-internal-notes">
            <b>Catatan internal</b>
            <p>{p.internal_notes}</p>
          </div>
        )}
        {canChange && (
          <StatusPicker key={p.status} p={p} user={user} statuses={statuses} reload={reload} />
        )}
      </section>
      <section className="panel panel-padding">
        <h2 className="detail-heading">Perjalanan project</h2>
        <div className="workflow-list">
          {statuses.map((s, i) => (
            <div
              key={s}
              data-testid={`workflow-step-${i}`}
              className={`workflow-step ${i < idx ? "done" : ""} ${i === idx ? "current" : ""}`}
            >
              <span>{i < idx ? <Check size={12} /> : i + 1}</span>
              <span>{s}</span>
              {i === idx && <Badge>Aktif</Badge>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
