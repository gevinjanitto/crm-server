import React, { useState } from "react";
import {
  Wallet,
  Code2,
  Server,
  TrendingUp,
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  Wrench,
} from "lucide-react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { ChartFrame as ResponsiveContainer } from "../components/ChartFrame";
import { useData, money, compact, download } from "../lib/api";
import { PageHead, Loading, ErrorState, Badge, ExportButton, CountUp } from "../components/Common";
import { CostTypesPanel } from "../components/CostTypes";
import { YearSelect } from "../components/YearControls";
import { groupEntriesByYear, projectEntries, entryYears, currentYear, sortYears, yearLabel } from "../lib/projectYears";
// Maintenance rows only count the maintenance fee, never the original project value or costs.
const financeEntry = (e) => e.is_maintenance_entry ? { ...e, value: e.maintenance_cost || 0, development_cost: 0, server_cost: 0, other_cost: 0 } : e;
const profitOf = (p) => p.value - (p.development_cost || 0) - (p.server_cost || 0) - (p.other_cost || 0);
const FinanceRows = ({ rows }) => (
  <div className="table-wrap">
    <table className="data-table" data-testid="finance-table">
      <thead>
        <tr>
          <th>Project</th>
          <th>Nilai / biaya maintenance</th>
          <th>Development</th>
          <th>Server</th>
          <th>Lainnya</th>
          <th>Profit</th>
          <th>Margin</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p, i) => {
          const pr = profitOf(p);
          const tid = p.is_maintenance_entry ? `${p.id}-maint` : p.id;
          return (
            <motion.tr key={p.entry_key} className={p.is_maintenance_entry ? "maintenance-entry-row" : undefined} data-testid={`finance-row-${tid}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.04, ease: "easeOut" }}>
              <td>
                <Link to={`/projects/${p.id}`} data-testid={`finance-project-${tid}`}>
                  {p.name}
                  <ArrowUpRight size={12} style={{ display: "inline", marginLeft: 5 }} />
                </Link>
                {p.is_maintenance_entry && <span className="maintenance-entry-chip" data-testid={`finance-maint-chip-${p.id}`}><Wrench size={11} /> Biaya maintenance · {p.maintenance_count}x</span>}
              </td>
              <td data-testid={`finance-value-${tid}`}>{money(p.value)}</td>
              <td>{money(p.development_cost)}</td>
              <td>{money(p.server_cost)}</td>
              <td>{money(p.other_cost)}</td>
              <td style={{ color: pr >= 0 ? "#6dc4a2" : "#e48491" }}>{money(pr)}</td>
              <td>{p.value ? Math.round((pr / p.value) * 100) : 0}%</td>
            </motion.tr>
          );
        })}
      </tbody>
    </table>
  </div>
);
const FinanceYearGroups = ({ projects }) => {
  const [open, setOpen] = useState({});
  const groups = groupEntriesByYear(projects);
  if (!groups.length) return <div className="panel panel-padding" data-testid="finance-empty">Belum ada project pada tahun ini.</div>;
  return (
    <div className="project-year-groups" data-testid="finance-year-groups">
      {groups.map(([year, rows]) => {
        const closed = !(open[year] ?? (year === currentYear() || groups.length === 1));
        const total = rows.reduce((a, p) => a + p.value, 0);
        return (
          <section className="project-year-group" key={year} data-testid={`finance-year-group-${year}`}>
            <h2 className="project-year-heading">
              <button type="button" className="project-year-toggle" data-testid={`finance-year-toggle-${year}`} aria-expanded={!closed} onClick={() => setOpen((o) => ({ ...o, [year]: closed }))}>
                <CalendarDays size={19} aria-hidden="true" />
                <span className="project-year-label">{yearLabel(year)}</span>
                <span className="project-year-count" data-testid={`finance-year-count-${year}`}>{rows.filter((r) => !r.is_maintenance_entry).length} project{rows.some((r) => r.is_maintenance_entry) ? ` · ${rows.filter((r) => r.is_maintenance_entry).length} maintenance` : ""} · Rp {compact(total)}</span>
                <ChevronDown size={18} aria-hidden="true" className={`project-year-chevron ${closed ? "is-collapsed" : ""}`} />
              </button>
            </h2>
            {!closed && <div className="panel project-year-panel" data-testid={`finance-year-body-${year}`}><FinanceRows rows={rows} /></div>}
          </section>
        );
      })}
    </div>
  );
};
export default function Finance() {
  const { data: all, loading, error, reload } = useData("/projects");
  const [year, setYear] = useState(currentYear());
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const years = sortYears([...entryYears(all), currentYear()]);
  const entries = projectEntries(all).map(financeEntry);
  const data = year === "all" ? entries : entries.filter((p) => p.entry_year === year);
  const totals = data.reduce(
      (a, p) => ({
        value: a.value + p.value,
        development: a.development + (p.development_cost || 0),
        server: a.server + (p.server_cost || 0),
        other: a.other + (p.other_cost || 0),
      }),
      { value: 0, development: 0, server: 0, other: 0 },
    ),
    profit = totals.value - totals.development - totals.server - totals.other;
  return (
    <>
      <PageHead
        eyebrow="FINANCIAL OVERVIEW"
        title="Keuangan"
        description={`Setiap angka, perspektif baru untuk bisnis Anda — ${year === "all" ? "semua tahun" : `tahun ${yearLabel(year)}`}.`}
      >
        <YearSelect testid="finance-year-filter" value={year} years={years} onChange={setYear} />
        <ExportButton
          testid="export-finance"
          className="primary-button"
          onExport={() =>
            download("/reports/projects.xlsx", "laporan-keuangan-maiharta.xlsx")
          }
        >
          Ekspor laporan
        </ExportButton>
      </PageHead>
      <div className="finance-summary">
        {[
          ["Total nilai project", totals.value, Wallet],
          ["Biaya development", totals.development, Code2],
          ["Biaya server", totals.server, Server],
          ["Biaya lainnya", totals.other, Wallet],
          ["Estimasi keuntungan", profit, TrendingUp],
        ].map(([n, v, Icon], i) => (
          <motion.div
            className="finance-card"
            key={n}
            data-testid={`finance-stat-${i}`}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: i * 0.08, ease: "easeOut" }}
          >
            <small>
              <Icon size={15} />
              {n}
            </small>
            <b>
              Rp <CountUp value={v} format={compact} />
            </b>
          </motion.div>
        ))}
      </div>
      <CostTypesPanel />
      <div className="panel panel-padding" style={{ marginBottom: 27 }}>
        <div className="section-heading">
          <h2>Nilai & profit per project</h2>
          <div className="chart-legend">
            <span>
              <i />
              Nilai project
            </span>
            <span>
              <i />
              Profit
            </span>
          </div>
        </div>
        <div style={{ height: 245 }} data-testid="finance-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data.map((p) => ({
                name: p.is_maintenance_entry ? `${p.code} (M)` : p.code,
                nilai: p.value / 1e6,
                profit: profitOf(p) / 1e6,
              }))}
              barGap={6}
              margin={{ left: -20, top: 15, right: 5, bottom: 0 }}
            >
              <CartesianGrid
                stroke="var(--line)"
                vertical={false}
                strokeDasharray="3 5"
              />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#8993a7", fontSize: 9 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#8993a7", fontSize: 9 }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  fontSize: 11,
                  borderRadius: 6,
                }}
                formatter={(v, n) => [`${v} jt`, n]}
              />
              <Bar
                dataKey="nilai"
                name="Nilai"
                fill="#5984ef"
                radius={[3, 3, 0, 0]}
                maxBarSize={28}
              />
              <Bar
                dataKey="profit"
                name="Profit"
                fill="#62b7a6"
                radius={[3, 3, 0, 0]}
                maxBarSize={28}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <FinanceYearGroups key={year} projects={data} />
    </>
  );
}
