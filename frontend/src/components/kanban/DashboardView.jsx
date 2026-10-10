import React from "react";
import { fmtDuration, PRIORITY_COLOR, SOURCE_LABEL, summarizeTasks } from "./helpers";

const Bars = ({ rows, color }) => {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="ck-bars">
      {rows.map((r) => (
        <div className="ck-bar-row" key={r.name}>
          <span className="ck-bar-label">{r.name}</span>
          <div className="ck-bar-track">
            <div
              style={{ width: `${(r.count / max) * 100}%`, background: r.color || color(r.name) }}
            />
          </div>
          <b>{r.count}</b>
        </div>
      ))}
    </div>
  );
};

export const DashboardView = ({ tasks, statuses }) => {
  const data = summarizeTasks(tasks, statuses);
  const pct = data.total ? Math.round((data.done / data.total) * 100) : 0;
  const kpis = [
    ["Total task", data.total, ""],
    ["Selesai", `${pct}%`, `${data.done} dari ${data.total}`],
    ["Terlambat", data.overdue, "melewati target", data.overdue ? "bad" : ""],
    ["Belum ditugaskan", data.unassigned, "perlu PIC"],
    ["Selesai 7 hari", data.completed_week, "task minggu ini", "good"],
    ["Waktu tercatat", fmtDuration(data.time_total), `estimasi ${data.estimate_total} jam`],
  ];
  return (
    <div className="ck-dash" data-testid="kanban-dashboard">
      <div className="ck-kpis">
        {kpis.map(([label, value, sub, tone], i) => (
          <div className={`ck-kpi ${tone || ""}`} key={label} data-testid={`kpi-${i}`}>
            <small>{label}</small>
            <b>{value}</b>
            {sub && <span>{sub}</span>}
          </div>
        ))}
      </div>
      <div className="ck-dash-grid">
        <section className="ck-panel">
          <h4>Task per status</h4>
          <Bars rows={data.by_status} color={() => "#3b82f6"} />
        </section>
        <section className="ck-panel">
          <h4>Task per prioritas</h4>
          <Bars rows={data.by_priority} color={(n) => PRIORITY_COLOR[n]} />
        </section>
        <section className="ck-panel">
          <h4>Sumber task</h4>
          <Bars
            rows={data.by_source.map((s) => ({ ...s, name: SOURCE_LABEL[s.name] }))}
            color={() => "#8b5cf6"}
          />
        </section>
        <section className="ck-panel">
          <h4>Beban kerja tim</h4>
          <table className="ck-table compact" data-testid="workload-table">
            <thead>
              <tr>
                <th>Anggota</th>
                <th>Task</th>
                <th>Selesai</th>
                <th>Waktu</th>
                <th>Progress</th>
              </tr>
            </thead>
            <tbody>
              {data.by_assignee.map((a) => (
                <tr key={a.name}>
                  <td>
                    <b>{a.name}</b>
                  </td>
                  <td>{a.total}</td>
                  <td>{a.done}</td>
                  <td>{fmtDuration(a.time)}</td>
                  <td>
                    <div className="ck-bar-track small">
                      <div style={{ width: `${a.total ? (a.done / a.total) * 100 : 0}%`, background: "#10b981" }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
};
