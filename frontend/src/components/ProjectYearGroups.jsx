import React, { useEffect, useState } from 'react';
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { ProjectTable } from './ProjectTable';
import { Empty } from './Common';
import { PageSizeSelect } from './YearControls';
import { groupEntriesByYear, currentYear } from '../lib/projectYears';

const DEFAULT_SIZE = 10;

export const ProjectYearGroups = ({ projects, filterKey }) => {
  const [open, setOpen] = useState({});
  const [pageByYear, setPageByYear] = useState({});
  const [sizeByYear, setSizeByYear] = useState({});
  useEffect(() => { setPageByYear({}); setOpen({}); }, [filterKey]);
  const groups = groupEntriesByYear(projects);
  if (!groups.length) return <Empty message="Belum ada project yang sesuai." />;
  return <div className="project-year-groups" data-testid="project-year-groups">
    {groups.map(([year, rows]) => {
      const size = sizeByYear[year] ?? DEFAULT_SIZE;
      const per = size || rows.length || 1;
      const pages = Math.max(1, Math.ceil(rows.length / per));
      const page = Math.min(pageByYear[year] || 1, pages);
      const start = (page - 1) * per;
      const label = year;
      const maintCount = rows.filter(r => r.is_maintenance_entry).length;
      const closed = !(open[year] ?? (year === currentYear() || groups.length === 1));
      const setPage = next => setPageByYear(previous => ({ ...previous, [year]: next }));
      return <section className="project-year-group" key={year} data-testid={`projects-year-group-${year}`} aria-labelledby={`projects-year-heading-${year}`}>
        <h2 className="project-year-heading" id={`projects-year-heading-${year}`}>
          <button type="button" className="project-year-toggle" data-testid={`projects-year-toggle-${year}`} aria-expanded={!closed} aria-controls={`projects-year-body-${year}`} onClick={() => setOpen(previous => ({...previous,[year]:closed}))}>
            <CalendarDays size={19} aria-hidden="true"/>
            <span className="project-year-label" data-testid={`projects-year-title-${year}`}>{label}</span>
            <span className="project-year-count" data-testid={`projects-year-count-${year}`}>{rows.length - maintCount} project{maintCount ? ` · ${maintCount} maintenance` : ''}</span>
            <ChevronDown size={18} aria-hidden="true" className={`project-year-chevron ${closed ? 'is-collapsed' : ''}`}/>
          </button>
        </h2>
        <div className="panel project-year-panel" id={`projects-year-body-${year}`} data-testid={`projects-year-body-${year}`} hidden={closed}>
          {!closed && <>
            <ProjectTable projects={rows.slice(start, start + per)} testId={`projects-table-${year}`} />
            <div className="table-footer">
              <span data-testid={`projects-year-page-count-${year}`}>{start + 1}–{Math.min(start + per, rows.length)} dari {rows.length} project</span>
              <PageSizeSelect testid={`projects-page-size-${year}`} value={size} onChange={n => { setSizeByYear(previous => ({ ...previous, [year]: n })); setPage(1); }} />
              {pages > 1 && <div className="pagination" aria-label={`Halaman project ${label}`}>
                <button type="button" data-testid={`projects-prev-page-${year}`} disabled={page === 1} onClick={() => setPage(page - 1)} title={`Halaman sebelumnya — ${label}`}><ChevronLeft size={13}/></button>
                <span data-testid={`projects-current-page-${year}`}>{page} / {pages}</span>
                <button type="button" data-testid={`projects-next-page-${year}`} disabled={page >= pages} onClick={() => setPage(page + 1)} title={`Halaman selanjutnya — ${label}`}><ChevronRight size={13}/></button>
              </div>}
            </div>
          </>}
        </div>
      </section>;
    })}
  </div>;
};
