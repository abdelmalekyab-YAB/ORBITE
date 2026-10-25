import { useNavigate } from "react-router-dom";
import { HealthBadge, Loading } from "../../components/bits";
import { useApi } from "../../lib/hooks";
import type { Project } from "../../lib/types";

export default function Projects() {
  const { data } = useApi<Project[]>("/projects");
  const navigate = useNavigate();
  if (!data) return <Loading />;
  return (
    <>
      <h1 style={{ marginBottom: 18 }}>Projets</h1>
      <div className="g3">
        {data.map((p) => (
          <div
            className="ph"
            key={p.key}
            role="button"
            tabIndex={0}
            onClick={() => navigate(`/dig/projets/${p.key}`)}
            onKeyDown={(e) => e.key === "Enter" && navigate(`/dig/projets/${p.key}`)}
          >
            <HealthBadge health={p.health} style={{ position: "absolute", right: 14, top: 14 }} />
            <h2>{p.name}</h2>
            <div className="c">
              {p.key} · {p.client} · {p.lead?.name ?? "sans responsable"}
            </div>
            <div className="why">{p.description}</div>
            <div className="row">
              <div>
                <b>{p.counts.open}</b>ouvertes
              </div>
              <div>
                <b>{p.counts.client}</b>chez client
              </div>
              <div>
                <b>{p.counts.delivered}</b>livrées
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
