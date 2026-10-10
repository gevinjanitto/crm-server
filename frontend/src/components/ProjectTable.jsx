import React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Globe,
  ShoppingBag,
  PenTool,
  AppWindow,
} from "lucide-react";
import { Badge, Progress, Empty } from "./Common";
import { dateLabel, initials } from "../lib/api";
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
            return (
              <motion.tr
                key={p.id}
                data-testid={`project-row-${p.id}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: i * 0.05, ease: "easeOut" }}
              >
                <td className="project-table-title-cell">
                  <Link
                    to={`/projects/${p.id}`}
                    className="table-name"
                    data-testid={`project-link-${p.id}`}
                  >
                    <span className={`project-glyph glyph-${i % 4}`}>
                      <Icon size={16} />
                    </span>
                    <div>
                      <b>{p.name}</b>
                      <small>
                        {p.code} · {(p.platforms || [p.category]).join(", ")}
                      </small>
                    </div>
                  </Link>
                </td>
                <td className="hide-mobile">{p.client_name}</td>
                <td data-label="Status" className="project-table-status-cell">
                  <Badge id={`project-status-${p.id}`}>{p.status}</Badge>
                </td>
                <td data-label="Progress" className="project-table-progress-cell">
                  <Progress
                    id={`project-progress-${p.id}`}
                    value={p.progress}
                  />
                </td>
                <td className="hide-mobile">{dateLabel(p.due_date)}</td>
                <td className="hide-mobile">
                  <span
                    className="avatar small"
                    title={`${p.assigned_to.length} developer`}
                    data-testid={`project-team-${p.id}`}
                  >
                    {p.assigned_to.length || "—"}
                  </span>
                </td>
                <td className="project-table-open-cell">
                  <Link
                    to={`/projects/${p.id}`}
                    className="icon-button"
                    title="Detail project"
                    data-testid={`project-open-${p.id}`}
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
