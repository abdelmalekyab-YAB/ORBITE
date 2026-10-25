import { useState } from "react";
import { Empty, Loading } from "../../components/bits";
import ExportButton from "../../components/ExportButton";
import ReqRow from "../../components/ReqRow";
import type { Ticket } from "../../lib/types";

type Segment = "all" | "you" | "dig" | "done";

export default function ClientRequests({ tickets, showProject }: { tickets: Ticket[] | null; showProject: boolean }) {
  const [seg, setSeg] = useState<Segment>("all");
  const [q, setQ] = useState("");
  if (!tickets) return <Loading />;

  const open = tickets.filter((t) => !t.is_closed);
  const bySeg: Record<Segment, Ticket[]> = {
    all: open,
    you: open.filter((t) => t.ball === "client"),
    dig: open.filter((t) => t.ball === "digitalia"),
    done: tickets.filter((t) => t.is_closed),
  };
  const labels: [Segment, string][] = [
    ["all", "Toutes"],
    ["you", "À vous"],
    ["dig", "Chez Digitalia"],
    ["done", "Livrées"],
  ];
  const needle = q.trim().toLowerCase();
  const list = bySeg[seg].filter(
    (t) => !needle || t.title.toLowerCase().includes(needle) || t.ref.toLowerCase().includes(needle),
  );

  return (
    <>
      <h1 style={{ marginBottom: 16 }}>Mes demandes</h1>
      <div className="toolbar">
        <div className="chips">
          {labels.map(([k, l]) => (
            <button key={k} className={`chip ${seg === k ? "on" : ""}`} onClick={() => setSeg(k)}>
              {l} <span className="muted">{bySeg[k].length}</span>
            </button>
          ))}
        </div>
        <div className="search">
          <input placeholder="Rechercher…" aria-label="Rechercher" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <ExportButton path="/tickets/export.csv" filename="mes-demandes.csv" />
      </div>
      {list.length ? (
        list.map((t) => <ReqRow key={t.id} ticket={t} showProject={showProject} />)
      ) : (
        <div className="card">
          <Empty title="Aucune demande ici" />
        </div>
      )}
    </>
  );
}
