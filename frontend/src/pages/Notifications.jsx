import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCheck, BellOff } from "lucide-react";
import { toast } from "sonner";
import { useData, api } from "../lib/api";
import { PageHead, Loading, ErrorState } from "../components/Common";
import { NotifItem } from "../components/NotificationBell";

export default function Notifications() {
  const { data, loading, error, reload, setData } = useData("/notifications"),
    [filter, setFilter] = useState("semua"),
    navigate = useNavigate();
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const items = data.items.filter((n) => filter === "semua" || !n.read);
  const openItem = async (n) => {
    if (!n.read) {
      await api.post(`/notifications/${n.id}/read`).catch(() => {});
      setData({
        ...data,
        unread: Math.max(0, data.unread - 1),
        items: data.items.map((x) => (x.id === n.id ? { ...x, read: true } : x)),
      });
    }
    navigate(n.link || "/");
  };
  const remove = async (n) => {
    try {
      await api.delete(`/notifications/${n.id}`);
      setData({
        ...data,
        unread: n.read ? data.unread : Math.max(0, data.unread - 1),
        items: data.items.filter((x) => x.id !== n.id),
      });
    } catch (e) {
      toast.error("Notifikasi tidak dapat dihapus.");
    }
  };
  const readAll = async () => {
    await api.post("/notifications/read-all").catch(() => {});
    setData({ ...data, unread: 0, items: data.items.map((x) => ({ ...x, read: true })) });
    toast.success("Semua notifikasi ditandai dibaca");
  };
  return (
    <div className="notif-page">
      <PageHead
        eyebrow="AKTIVITAS"
        title="Notifikasi"
        description={
          data.unread
            ? `${data.unread} notifikasi belum dibaca.`
            : "Semua notifikasi sudah Anda baca."
        }
      >
        {data.unread > 0 && (
          <button
            type="button"
            className="secondary-button"
            onClick={readAll}
            data-testid="notifications-read-all"
          >
            <CheckCheck size={16} /> Tandai semua dibaca
          </button>
        )}
      </PageHead>
      <div className="list-toolbar">
        <div className="filter-tabs">
          {[
            ["semua", "Semua", data.items.length],
            ["belum", "Belum dibaca", data.unread],
          ].map(([k, label, count]) => (
            <button
              key={k}
              type="button"
              className={`filter-tab ${filter === k ? "active" : ""}`}
              onClick={() => setFilter(k)}
              data-testid={`notifications-tab-${k}`}
            >
              {label}
              <span>{count}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="panel" data-testid="notifications-list">
        {items.length ? (
          items.map((n) => (
            <NotifItem key={n.id} n={n} onOpen={openItem} onRemove={remove} />
          ))
        ) : (
          <div className="notif-empty">
            <BellOff size={26} />
            Tidak ada notifikasi.
          </div>
        )}
      </div>
    </div>
  );
}
