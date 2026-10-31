import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  Bell,
  BellOff,
  CheckCheck,
  Ticket,
  FolderKanban,
  UserCheck,
  ListChecks,
  Wallet,
  FileText,
  Rocket,
  Info,
} from "lucide-react";
import { api } from "../lib/api";

export const notifIcon = (kind) =>
  ({
    tiket: Ticket,
    project: FolderKanban,
    penugasan: UserCheck,
    task: ListChecks,
    fitur: ListChecks,
    keuangan: Wallet,
    dokumen: FileText,
    deployment: Rocket,
  })[kind] || Info;

export const timeAgo = (iso) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "baru saja";
  if (s < 3600) return `${Math.floor(s / 60)} menit lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)} jam lalu`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} hari lalu`;
  return new Date(iso).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
  });
};

export function NotifItem({ n, onOpen, onRemove, compact }) {
  const Icon = notifIcon(n.kind);
  return (
    <div
      className={`notif-item ${n.read ? "" : "unread"}`}
      data-testid={`notif-item-${n.id}`}
    >
      <button
        type="button"
        className="notif-icon-btn"
        style={{ display: "contents", background: "none", border: 0 }}
        onClick={() => onOpen(n)}
        data-testid={`notif-open-${n.id}`}
      >
        <span className={`notif-icon ${n.kind}`}>
          <Icon size={16} />
        </span>
        <span className="notif-body">
          <b>{n.title}</b>
          <p>{n.message}</p>
          <time>
            {timeAgo(n.created_at)}
            {n.actor_name && n.actor_name !== "Sistem" ? ` · ${n.actor_name}` : ""}
          </time>
        </span>
      </button>
      {!n.read && <span className="notif-dot" />}
      {!compact && onRemove && (
        <button
          type="button"
          className="notif-item-remove"
          title="Hapus notifikasi"
          data-testid={`notif-remove-${n.id}`}
          onClick={() => onRemove(n)}
        >
          ×
        </button>
      )}
    </div>
  );
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false),
    [unread, setUnread] = useState(0),
    [items, setItems] = useState([]),
    wrap = useRef(null),
    navigate = useNavigate();
  const poll = useCallback(async () => {
    try {
      const r = await api.get("/notifications/unread-count");
      setUnread(r.data.unread);
    } catch (e) {}
  }, []);
  const load = useCallback(async () => {
    try {
      const r = await api.get("/notifications");
      setItems(r.data.items.slice(0, 8));
      setUnread(r.data.unread);
    } catch (e) {}
  }, []);
  useEffect(() => {
    poll();
    const id = setInterval(poll, 30000);
    const onFocus = () => poll();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [poll]);
  useEffect(() => {
    if (open) load();
  }, [open, load]);
  useEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (wrap.current && !wrap.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const openItem = async (n) => {
    if (!n.read) {
      await api.post(`/notifications/${n.id}/read`).catch(() => {});
      setUnread((u) => Math.max(0, u - 1));
    }
    setOpen(false);
    navigate(n.link || "/notifications");
  };
  const readAll = async () => {
    await api.post("/notifications/read-all").catch(() => {});
    setItems((l) => l.map((n) => ({ ...n, read: true })));
    setUnread(0);
  };
  return (
    <div className="notif-wrap" ref={wrap}>
      <button
        type="button"
        className={`notif-bell ${open ? "open" : ""}`}
        data-testid="notification-bell"
        title="Notifikasi"
        onClick={() => setOpen(!open)}
      >
        <Bell size={18} />
        {unread > 0 && (
          <span className="notif-badge" data-testid="notification-badge">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="notif-panel" data-testid="notification-panel">
          <div className="notif-panel-head">
            <b>Notifikasi</b>
            {unread > 0 && (
              <button
                type="button"
                onClick={readAll}
                data-testid="notification-read-all"
              >
                <CheckCheck size={14} /> Tandai semua dibaca
              </button>
            )}
          </div>
          <div className="notif-list">
            {items.length ? (
              items.map((n) => (
                <NotifItem key={n.id} n={n} onOpen={openItem} compact />
              ))
            ) : (
              <div className="notif-empty" data-testid="notification-empty">
                <BellOff size={22} />
                Belum ada notifikasi untuk Anda.
              </div>
            )}
          </div>
          <div className="notif-panel-foot">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              data-testid="notification-view-all"
            >
              Lihat semua notifikasi
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
