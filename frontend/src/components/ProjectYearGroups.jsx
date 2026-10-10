import React, { useEffect, useState } from 'react';
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { ProjectTable } from './ProjectTable';
import { Empty } from './Common';
import { groupProjectsByStartYear } from '../lib/projectYears';

const PAGE_SIZE = 8;

export const ProjectYearGroups = ({ projects, filterKey }) => {
  const [collapsed, setCollapsed] = useState({});
  const [pageByYear, setPageByYear] = useState({});
  useEffect(() => { setPageByYear({}); setCollapsed({}); }, [filterKey]);
  const groups = groupProjectsByStartYear(projects);
  if (!groups.length) return <Empty message="Belum ada project yang sesuai." />;
  return <div className="project-year-groups" data-testid="project-year-groups">
    {groups.map(([year, rows]) => {
      const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
      const page = Math.min(pageByYear[year] || 1, pages);
      const start = (page - 1) * PAGE_SIZE;
      const label = year === 'undated' ? 'Belum ada tanggal mulai' : year;
      const closed = Boolean(collapsed[year]);
      const setPage = next => setPageByYear(previous => ({ ...previous, [year]: next }));
      return <section className="project-year-group" key={year} data-testid={`projects-year-group-${year}`} aria-labelledby={`projects-year-heading-${year}`}>
        <h2 className="project-year-heading" id={`projects-year-heading-${year}`}>
          <button type="button" className="project-year-toggle" data-testid={`projects-year-toggle-${year}`} aria-expanded={!closed} aria-controls={`projects-year-body-${year}`} onClick={() => setCollapsed(previous => ({...previous,[year]:!previous[year]}))}>
            <CalendarDays size={19} aria-hidden="true"/>
            <span className="project-year-label" data-testid={`projects-year-title-${year}`}>{label}</span>
            <span className="project-year-count" data-testid={`projects-year-count-${year}`}>{rows.length} project</span>
            <ChevronDown size={18} aria-hidden="true" className={`project-year-chevron ${closed ? 'is-collapsed' : ''}`}/>
          </button>
        </h2>
        <div className="panel project-year-panel" id={`projects-year-body-${year}`} data-testid={`projects-year-body-${year}`} hidden={closed}>
          {!closed && <>
            <ProjectTable projects={rows.slice(start, start + PAGE_SIZE)} testId={`projects-table-${year}`} />
            <div className="table-footer">
              <span data-testid={`projects-year-page-count-${year}`}>{start + 1}–{Math.min(start + PAGE_SIZE, rows.length)} dari {rows.length} project</span>
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