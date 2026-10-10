import React from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "./components/AuthProvider";
export { useAuth } from "./components/AuthProvider";
import Login from "./pages/Login";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";
import Clients from "./pages/Clients";
import Tickets from "./pages/Tickets";
import Finance from "./pages/Finance";
import WorkList from "./pages/WorkList";
import Users from "./pages/Users";
import Settings from "./pages/Settings";
import Trash from "./pages/Trash";
import Audit from "./pages/Audit";
import Notifications from "./pages/Notifications";
import NotificationGuide from './pages/NotificationGuide';
import Inbox from './pages/Inbox';
import Reminders from './pages/Reminders';
import { CodeLoader } from './components/CodeLoader';
import { BrandIntro } from './components/BrandIntro';
import "./App.css";
import "./modern.css";
import "./kanban.css";
import "./fixes.css";
import "./interaction.css";
import "./components/barong.css";
import "./components/code-loading.css";
import "./work-care.css";
import "./brand-experience.css";
import './requested-features.css';
import './components/status-picker.css';
import './reminder-inbox.css';
import { PROJECT_LIST_ROLES } from './lib/projectAccess';

function Protected({ children, roles }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <div className="app-loading auth-code-loading" data-testid="app-loading" role="status" aria-busy="true" aria-live="polite">
        <CodeLoader testId="auth-loading-code-animation" />
        <p data-testid="auth-loading-caption">Menyiapkan ruang kerja Anda...</p>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password && location.pathname !== "/settings")
    return <Navigate to="/settings" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <BrandIntro>
        <Toaster richColors position="top-right" />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="projects" element={<Protected roles={PROJECT_LIST_ROLES}><Projects /></Protected>} />
            <Route path="projects/:id" element={<ProjectDetail />} />
            <Route path="projects/:id/:section" element={<ProjectDetail />} />
            <Route path="kanban" element={<Navigate to="/projects" replace />} />
            <Route
              path="clients"
              element={
                <Protected roles={["Admin", "Admin Project", "Accounting"]}>
                  <Clients />
                </Protected>
              }
            />
            <Route
              path="tickets"
              element={
                <Protected
                  roles={["Admin", "Admin Project", "Developer", "Client"]}
                >
                  <Tickets />
                </Protected>
              }
            />
            <Route
              path="finance"
              element={
                <Protected roles={["Admin", "Accounting"]}>
                  <Finance />
                </Protected>
              }
            />
            <Route
              path="revisions"
              element={
                <Protected roles={["Admin", "Admin Project", "Developer"]}>
                  <WorkList kind="revisions" />
                </Protected>
              }
            />
            <Route
              path="maintenance"
              element={
                <Protected roles={["Admin", "Admin Project", "Developer"]}>
                  <WorkList kind="maintenances" />
                </Protected>
              }
            />
            <Route
              path="users"
              element={
                <Protected roles={["Admin"]}>
                  <Users />
                </Protected>
              }
            />
            <Route path="settings" element={<Settings />} />
            <Route path="settings/notifications-guide" element={<NotificationGuide/>} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="reminders" element={<Protected roles={["Admin"]}><Reminders /></Protected>} />
            <Route
              path="trash"
              element={
                <Protected roles={["Admin", "Admin Project"]}>
                  <Trash />
                </Protected>
              }
            />
            <Route
              path="audit"
              element={
                <Protected roles={["Admin"]}>
                  <Audit />
                </Protected>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </BrandIntro>
      </AuthProvider>
    </BrowserRouter>
  );
}
