import { useEffect, useRef, useState } from "react";
import { post } from "../lib/api";
import { fmtDT } from "../lib/format";
import { useApi } from "../lib/hooks";
import { Empty } from "./bits";
import { useUI } from "./UIContext";

interface Note {
  id: number;
  kind: string;
  title: string;
  ticket: { id: number; ref: string; title: string } | null;
  created_at: string;
  read_at: string | null;
}

/** Cloche de la topbar : notifications de l'utilisateur (rafraîchies chaque minute). */
export default function NotificationBell() {
  const { data, reload } = useApi<{ unread: number; results: Note[] }>("/notifications");
  const { openTicket } = useUI();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = window.setInterval(reload, 60_000);
    return () => window.clearInterval(id);
  }, [reload]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  async function openNote(n: Note) {
    if (!n.read_at) await post(`/notifications/${n.id}/read`, {});
    setOpen(false);
    reload();
    if (n.ticket) openTicket(n.ticket.id);
  }

  const unread = data?.unread ?? 0;
  return (
    <div ref={box} style={{ position: "relative" }}>
      <button
        className="btn ghost"
        aria-label={`Notifications${unread ? ` (${unread} non lues)` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        🔔
        {unread > 0 && (
          <span
            className="n"
            style={{
              background: "var(--grad)",
              color: "#fff",
              fontSize: 11,
              fontWeight: 700,
              borderRadius: 99,
              padding: "0 7px",
              lineHeight: "18px",
            }}
          >
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className="card"
          role="dialog"
          aria-label="Notifications"
          style={{
            position: "absolute",
            right: 0,
            top: 44,
            width: 360,
            maxHeight: 420,
            overflowY: "auto",
            zIndex: 30,
            padding: 12,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <h3>Notifications</h3>
            {unread > 0 && (
              <button
                className="btn ghost sm"
                onClick={async () => {
                  await post("/notifications/read-all", {});
                  reload();
                }}
              >
                Tout marquer lu
              </button>
            )}
          </div>
          {data?.results.length ? (
            data.results.map((n) => (
              <div
                key={n.id}
                className="ti"
                style={{ gridTemplateColumns: "1fr", marginBottom: 6, opacity: n.read_at ? 0.6 : 1 }}
                role="button"
                tabIndex={0}
                onClick={() => openNote(n)}
                onKeyDown={(e) => e.key === "Enter" && openNote(n)}
              >
                <div>
                  <div className="t">
                    {!n.read_at && "● "}
                    {n.title}
                  </div>
                  <div className="s">
                    {n.ticket ? `${n.ticket.title} · ` : ""}
                    {fmtDT(n.created_at)}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <Empty title="Rien de neuf" />
          )}
        </div>
      )}
    </div>
  );
}
