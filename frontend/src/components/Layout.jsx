import React, { useState, useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  UsersRound,
  Wallet,
  RotateCcw,
  Wrench,
  Ticket,
  ShieldCheck,
  Settings,
  Trash2,
  ScrollText,
  LogOut,
  Search,
  Menu,
  ChevronDown,
  X,
  Inbox,
  BellRing,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { TooltipProvider } from "./ui/tooltip";
import { useAuth } from "../App";
import { Footer } from "./Common";
import NotificationBell from "./NotificationBell";
import WelcomeDialog from "./WelcomeDialog";
import { OrbitBackdrop } from "./OrbitBackdrop";
import { initials } from "../lib/api";
import { LayoutGroup } from 'framer-motion';
import { SidebarNavItem } from './SidebarNavItem';
import { PROJECT_LIST_ROLES, canListProjects } from '../lib/projectAccess';
const nav = [
  ["/", "Dashboard", LayoutDashboard],
  ["/inbox", "Inbox", Inbox],
  ["/projects", "Semua Project", FolderKanban, PROJECT_LIST_ROLES],
  ["/clients", "Client", UsersRound, ["Admin", "Admin Project", "Accounting"]],
  ["/finance", "Keuangan", Wallet, ["Admin", "Accounting"]],
  ["/revisions", "Revisi", RotateCcw, ["Admin", "Admin Project", "Developer"]],
  ["/reminders", "Reminder", BellRing, ["Admin"]],
  [
    "/maintenance",
    "Maintenance",
    Wrench,
    ["Admin", "Admin Project", "Developer"],
  ],
  [
    "/tickets",
    "Tiket Client",
    Ticket,
    ["Admin", "Admin Project", "Developer", "Client"],
  ],
];
const preferences = [
  ["/users", "Manajemen User", ShieldCheck, ["Admin"]],
  ["/audit", "Audit Trail", ScrollText, ["Admin"]],
  ["/trash", "Recycle Bin", Trash2, ["Admin", "Admin Project"]],
  ["/settings", "Pengaturan", Settings],
];
const COLLAPSE_KEY = "maiharta_sidebar_collapsed";
export default function Layout() {
  const { user, logout } = useAuth(),
    location = useLocation(),
    navigate = useNavigate();
  const [open, setOpen] = useState(false),
    [search, setSearch] = useState(""),
    [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const toggleCollapsed = () => setCollapsed((value) => {
    localStorage.setItem(COLLAPSE_KEY, value ? "0" : "1");
    return !value;
  });
  // Keep project navigation mounted between tabs for the shared active indicator.
  const pageKey = location.pathname.match(/^\/projects\/[^/]+/)?.[0] || location.pathname;
  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
        document.querySelector('[data-testid="open-menu"]')?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);
  const title =
    nav.find((n) => n[0] === location.pathname)?.[1] ||
    (location.pathname.startsWith("/projects/")
      ? "Detail Project"
      : location.pathname === "/users"
        ? "Manajemen User"
        : location.pathname === "/trash"
          ? "Recycle Bin"
          : location.pathname === "/audit"
            ? "Audit Trail"
            : location.pathname === "/notifications"
              ? "Notifikasi"
              : "Pengaturan");
  return (
    <TooltipProvider>
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`} data-testid="app-shell">
      {open && (
        <button
          className="sidebar-backdrop"
          data-testid="sidebar-backdrop"
          aria-label="Tutup menu"
          onClick={() => setOpen(false)}
        />
      )}
      <button type="button" className="sidebar-edge-toggle" data-testid="sidebar-collapse-toggle"
        aria-label={collapsed ? "Perbesar menu" : "Perkecil menu"} title={collapsed ? "Perbesar menu" : "Perkecil menu"}
        aria-pressed={collapsed} onClick={toggleCollapsed}>
        {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
      </button>
      <aside id="workspace-sidebar" className={`sidebar ${open ? "open" : ""}`} aria-label="Menu workspace">
        <button type="button" className="sidebar-close" data-testid="close-menu" aria-label="Tutup menu" onClick={() => setOpen(false)}><X size={17} /></button>
        <NavLink
          to="/"
          className="sidebar-brand"
          data-testid="sidebar-logo-link"
        >
          <img
            src="/assets/logo-mark.webp"
            alt="MaiHarta"
            data-testid="sidebar-logo"
          />
          <span className="brand-text">
            <b>
              CRM <em>maiharta</em>
            </b>
            <small>PROJECT WORKSPACE</small>
          </span>
        </NavLink>
        <div className="nav-label" data-testid="main-menu-label">MENU UTAMA</div>
        <LayoutGroup id="main-navigation">
        <nav className="animated-main-navigation" aria-label="Menu utama">
          {nav
            .filter((n) => !n[3] || n[3].includes(user.role))
            .map(([path, label, Icon]) => (
              <SidebarNavItem key={path} path={path} label={label} icon={Icon} collapsed={collapsed} />
            ))}
        </nav>
        <div className="sidebar-lower animated-main-navigation">
          <div className="nav-label" data-testid="preferences-menu-label">PREFERENSI</div>
          <nav aria-label="Preferensi">
            {preferences.filter((item) => !item[3] || item[3].includes(user.role)).map(([path, label, Icon]) =>
              <SidebarNavItem key={path} path={path} label={label} icon={Icon} preference collapsed={collapsed} />)}
          </nav>
        </div>
        </LayoutGroup>
        <button
          className="sidebar-profile"
          data-testid="logout-button"
          onClick={() => logout()}
          title={collapsed ? `Keluar (${user.name})` : "Keluar"}
        >
          <span className="avatar">{initials(user.name)}</span>
          <span className="profile-copy">
            <b>{user.name}</b>
            <small>{user.role}</small>
          </span>
          <LogOut size={17} />
        </button>
      </aside>
      <div className={`main-shell ${location.pathname === "/" ? "dashboard-shell" : ""}`}>
        {location.pathname === "/" && <OrbitBackdrop variant="dashboard" />}
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              data-testid="open-menu"
              aria-label="Buka menu"
              aria-expanded={open}
              aria-controls="workspace-sidebar"
              onClick={() => setOpen(true)}
              title="Buka menu"
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <span className="crumb-divider">/</span>
            <b data-testid="breadcrumb-current">{title}</b>
          </div>
          <div className="topbar-actions">
            {canListProjects(user) && <form
              className="global-search"
              onSubmit={(e) => {
                e.preventDefault();
                navigate(`/projects?q=${encodeURIComponent(search)}`);
              }}
            >
              <Search size={16} />
              <input
                data-testid="global-search"
                placeholder="Cari project..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </form>}
            {canListProjects(user) && <span className="topbar-separator" />}
            <NotificationBell />
            <button
              className="topbar-profile"
              data-testid="topbar-profile"
              onClick={() => navigate("/settings")}
            >
              <span className="avatar small">{initials(user.name)}</span>
              <span>{user.name.split(" ")[0]}</span>
              <ChevronDown size={13} />
            </button>
          </div>
        </header>
        <main className="page-content route-transition" key={pageKey} data-testid="page-transition">
          <Outlet />
        </main>
        <Footer />
      </div>
      <WelcomeDialog />
    </div>
    </TooltipProvider>
  );
}
