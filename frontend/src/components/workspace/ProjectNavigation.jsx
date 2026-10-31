import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Layers3, FileText, Network, Timer, Target, Users, CalendarRange, Zap, BarChart3, BellRing, MoreHorizontal, ChevronDown, Check } from 'lucide-react';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '../ui/dropdown-menu';
import './navigation.css';
import { LayoutGroup, motion, useReducedMotion } from 'framer-motion';

export const workspaceTabs = [
  ['struktur', 'Struktur', Layers3], ['docs', 'Notes', FileText],
  ['whiteboard', 'Whiteboard', Network], ['sprint', 'Sprint', Timer],
  ['goals', 'Goals', Target], ['kapasitas', 'Kapasitas', Users],
  ['gantt', 'Gantt', CalendarRange], ['automasi', 'Automasi', Zap],
  ['laporan', 'Laporan', BarChart3], ['reminder', 'Reminder', BellRing],
];

export const visibleWorkspaceTabs = role => workspaceTabs.filter(([key]) =>
  (key !== 'reminder' || role === 'Admin') && (['Admin', 'Admin Project', 'Developer'].includes(role) || !['whiteboard', 'kapasitas', 'automasi'].includes(key)));

export const ProjectNavigation = ({ id, section, tabs, tab, role, ticketSummary }) => {
  const [open, setOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const indicator = <motion.span className="project-tab-indicator" layoutId="project-active-tab"
    data-testid="project-navigation-indicator" aria-hidden="true"
    transition={reducedMotion ? { duration: 0 } : { type: 'spring', stiffness: 480, damping: 38 }} />;
  useEffect(() => setOpen(false), [id, section]);
  const items = visibleWorkspaceTabs(role).filter(([key]) => key !== 'laporan');
  const active = items.some(([key]) => key === section);
  const reportActive = section === 'laporan';
  const reportLink = (
      <Link to={`/projects/${id}/laporan`} className={`detail-tab ${reportActive ? 'active' : ''}`}
        aria-current={reportActive ? 'page' : undefined} data-testid="detail-tab-laporan">
        Laporan{reportActive && indicator}
      </Link>
  );
  return (
    <LayoutGroup id={`project-navigation-${id}`}>
    <nav className="detail-tabs project-detail-navigation" aria-label="Navigasi project" data-testid="project-detail-navigation">
      {tabs.map(label => (<React.Fragment key={label}>
        <Link to={`/projects/${id}/${label.toLowerCase()}`}
          className={`detail-tab ${tab === label ? 'active' : ''}`}
          aria-current={tab === label ? 'page' : undefined}
          data-testid={`detail-tab-${label.toLowerCase()}`}>{label}{tab === label && indicator}
          {label === 'Tiket' && ticketSummary?.total > 0 && <span
            className={`project-ticket-badge ${ticketSummary.new > 0 ? 'has-new' : ''}`}
            title={`${ticketSummary.new} tiket baru · ${ticketSummary.active} aktif · ${ticketSummary.total} total`}
            aria-label={`${ticketSummary.new || ticketSummary.active || ticketSummary.total} ${ticketSummary.new ? 'tiket baru' : ticketSummary.active ? 'tiket aktif' : 'total tiket'}`}
            data-testid="project-ticket-count">{ticketSummary.new || ticketSummary.active || ticketSummary.total}</span>}
          </Link>
        {label === 'Ringkasan' && reportLink}
      </React.Fragment>))}
      <DropdownMenu open={open} onOpenChange={setOpen} modal={false}>
        <DropdownMenuTrigger asChild>
          <button type="button" className={`detail-tab project-more-trigger ${active ? 'active' : ''}`}
            onPointerDown={event => event.preventDefault()}
            onClick={() => setOpen(value => !value)}
            data-testid="project-more-trigger" aria-label="More — menu project lainnya">
            <MoreHorizontal size={17} /><span>More</span><ChevronDown size={14} />
            {active && indicator}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" sideOffset={8} collisionPadding={16} className="project-more-menu" data-testid="project-more-menu">
          {items.map(([key, label, Icon]) => (
            <DropdownMenuItem key={key} asChild>
              <Link to={`/projects/${id}/${key}`} onClick={() => setOpen(false)} className={section === key ? 'project-more-selected' : ''}
                data-testid={`workspace-nav-${key}`} aria-current={section === key ? 'page' : undefined}>
                <Icon size={16} /><span>{label}</span>{section === key && <Check size={15} className="project-more-check" />}
              </Link>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
    </LayoutGroup>
  );
};