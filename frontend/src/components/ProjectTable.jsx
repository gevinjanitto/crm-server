import React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Globe,
  ShoppingBag,
  PenTool,
  AppWindow,
  Wrench,
} from "lucide-react";
import { Badge, Progress, Empty } from "./Common";
import { dateLabel, initials, projectStatus } from "../lib/api";
const icons = [Globe, ShoppingBag, PenTool, AppWindow];
export const ProjectTable = ({ projects, compact = false, testId = 'projects-table' }) => (
  <div className="table-wrap">
    {!projects.length ? (
      <Empty message="Belum ada project yang sesuai." />
    ) : (
      <table className="data-table project-data-table" data-testid={testId}>
        <thead>
          <tr>
            <th>Nama project</th>
            <th className="hide-mobile">Client</th>
            <th>Status</th>
            <th>Progress</th>
            <th className="hide-mobile">Deadline</th>
            <th className="hide-mobile">Tim</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {projects.map((p, i) => {
            const Icon = icons[i % 4];
            const m = p.is_maintenance_entry;
            const tid = m ? `${p.id}-maint` : p.id;
            return (
              <motion.tr
                key={p.entry_key || p.id}
                data-testid={`project-row-${tid}`}
                className={m ? "maintenance-entry-row" : undefined}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: i * 0.05, ease: "easeOut" }}
              >
                <td className="project-table-title-cell">
                  <Link
                    to={`/projects/${p.id}`}
                    className="table-name"
                    data-testid={`project-link-${tid}`}
                  >
                    <span className={`project-glyph glyph-${i % 4}`}>
                      <Icon size={16} />
                    </span>
                    <div>
                      <b>{p.name}</b>
                      <small>
                        {p.code} · {(p.platforms || [p.category]).join(", ")}
                      </small>
                      {m ? (
                        <span className="maintenance-entry-chip" data-testid={`project-maint-chip-${p.id}`}>
                          <Wrench size={11} /> {p.maintenance_group_name || `Maintenance ${p.maintenance_year}`}
                        </span>
                      ) : p.maintenance_year ? (
                        <span className="completion-entry-chip" data-testid={`project-done-chip-${p.id}`}>
                          Selesai {p.completion_year}
                        </span>
                      ) : null}
                    </div>
                  </Link>
                </td>
                <td className="hide-mobile">{p.client_name}</td>
                <td data-label="Status" className="project-table-status-cell">
                  <Badge id={`project-status-${tid}`}>{projectStatus(p)}</Badge>
                </td>
                <td data-label="Progress" className="project-table-progress-cell">
                  <Progress
                    id={`project-progress-${tid}`}
                    value={p.progress}
                  />
                </td>
                <td className="hide-mobile">{dateLabel(p.due_date)}</td>
                <td className="hide-mobile">
                  <span
                    className="avatar small"
                    title={`${p.assigned_to.length} developer`}
                    data-testid={`project-team-${tid}`}
                  >
                    {p.assigned_to.length || "—"}
                  </span>
                </td>
                <td className="project-table-open-cell">
                  <Link
                    to={`/projects/${p.id}`}
                    className="icon-button"
                    title="Detail project"
                    data-testid={`project-open-${tid}`}
                  >
                    <ArrowUpRight size={15} />
                  </Link>
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    )}
  </div>
);
