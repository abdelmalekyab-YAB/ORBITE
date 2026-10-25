import { useState } from "react";
import { useMe } from "../../auth/AuthContext";
import { Loading } from "../../components/bits";
import Roadmap from "../../components/Roadmap";
import type { Ticket } from "../../lib/types";
import type { Scope } from "./ClientSpace";

export default function ClientRoadmap({ tickets, scope }: { tickets: Ticket[] | null; scope: Scope }) {
  const me = useMe();
  const [chosen, setChosen] = useState(me.projects[0]?.key);
  const project = scope === "all" ? chosen : scope;
  if (!tickets) return <Loading />;
  return (
    <>
      <h1 style={{ marginBottom: 6 }}>Feuille de route</h1>
      <p className="hint" style={{ marginBottom: 18 }}>
        Les versions prévues et ce qu'elles contiennent. Les dates sont des objectifs, mis à jour par Digitalia.
      </p>
      {scope === "all" && me.projects.length > 1 && (
        <div className="chips" style={{ marginBottom: 16 }}>
          {me.projects.map((p) => (
            <button key={p.key} className={`chip ${p.key === project ? "on" : ""}`} onClick={() => setChosen(p.key)}>
              {p.name}
            </button>
          ))}
        </div>
      )}
      {project && <Roadmap key={project} project={project} tickets={tickets} />}
    </>
  );
}
