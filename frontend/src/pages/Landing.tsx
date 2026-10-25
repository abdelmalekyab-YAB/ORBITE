import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

// Accueil public repris de maquette/orbit-maquette.html (fond étoilé + ondes, orbites animées).
const SATELLITES: [string, string, number, number, string][] = [
  // Page publique : aucun nom de client (ni réel ni inventé), seulement ce que fait Orbit.
  ["Demandes", "#7c3aed", 6, 38, "0s"],
  ["Tests", "#a04bb5", 20, 26, "-9s"],
  ["Livraisons", "#c2410c", 6, 38, "-19s"],
  ["Vous ?", "#0b8a9c", 20, 26, "-13s"],
];
const DOT_LEFT = [16, 30, 44, 16, 30, 44];

function useStars(ref: React.RefObject<HTMLCanvasElement>) {
  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext?.("2d");
    if (!c || !ctx) return;
    let W = 0,
      H = 0,
      raf = 0;
    let pts: { x: number; y: number; z: number; v: number }[] = [];
    const resize = () => {
      W = c.width = c.offsetWidth;
      H = c.height = c.offsetHeight;
      pts = Array.from({ length: Math.min(160, W / 8) }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        z: Math.random() * 0.6 + 0.2,
        v: Math.random() * 0.2 + 0.05,
      }));
    };
    resize();
    window.addEventListener("resize", resize);
    const frame = () => {
      ctx.clearRect(0, 0, W, H);
      const g = ctx.createRadialGradient(W * 0.75, H * 0.3, 20, W * 0.75, H * 0.3, W * 0.6);
      g.addColorStop(0, "rgba(124,58,237,.22)");
      g.addColorStop(0.5, "rgba(224,75,255,.06)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "rgba(168,85,247,.10)";
      ctx.lineWidth = 1;
      for (let i = 0; i < 7; i++) {
        ctx.beginPath();
        for (let x = 0; x <= W; x += 20) {
          const y = H * 0.55 + i * 26 + Math.sin(x / 140 + i * 0.7 + performance.now() / 2600) * 22 + Math.sin(x / 47 + i) * 6;
          if (x) ctx.lineTo(x, y);
          else ctx.moveTo(x, y);
        }
        ctx.stroke();
      }
      pts.forEach((p) => {
        p.y -= p.v;
        if (p.y < 0) {
          p.y = H;
          p.x = Math.random() * W;
        }
        ctx.fillStyle = `rgba(255,255,255,${p.z})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.z * 1.4, 0, 7);
        ctx.fill();
      });
      raf = requestAnimationFrame(frame);
    };
    frame();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [ref]);
}

export default function Landing() {
  const canvas = useRef<HTMLCanvasElement>(null);
  useStars(canvas);
  return (
    <div className="land">
      <canvas ref={canvas} />
      <div className="lt">
        <div className="dl">
          <img src={`${import.meta.env.BASE_URL}logo-digitalia.png`} alt="Digitalia" />
          DIGITALIA
        </div>
        <span className="sp" />
        <Link to="/login" className="btn">
          Se connecter
        </Link>
      </div>
      <div className="lb">
        <div>
          <div className="tagl">✦ DÉVELOPPÉ PAR DIGITALIA POUR SES CLIENTS</div>
          <h1>
            Orbit
            <br />
            <span>vos projets, en orbite autour de vous</span>
          </h1>
          <p className="lead">
            Orbit est l'espace commun entre Digitalia et chacun de ses clients : suivez l'état de vos projets en production,
            signalez un problème, demandez une évolution, testez ce qui est livré. À chaque instant, vous savez qui a la main.
          </p>
          <div className="cta">
            <Link to="/login" className="btn white">
              Accéder à mon espace →
            </Link>
            <a className="btn ghost" href="https://digitalia-ltd.com" target="_blank" rel="noopener noreferrer">
              digitalia-ltd.com
            </a>
          </div>
          <div className="feat">
            <div>
              <b>Transparence</b>
              <span>L'état réel de chaque demande, sans relancer.</span>
            </div>
            <div>
              <b>Un seul endroit</b>
              <span>Bugs, évolutions, questions, tests : tout passe par Orbit.</span>
            </div>
            <div>
              <b>La balle est chez qui</b>
              <span>Chez vous ou chez Digitalia, c'est toujours clair.</span>
            </div>
          </div>
        </div>
        <div className="orb" aria-hidden="true">
          <div className="ring r1" />
          <div className="ring r2" />
          <div className="ring r3" />
          {SATELLITES.map(([name, color, left, duration, delay]) => (
            <div key={name} className="sat" style={{ animationDuration: `${duration}s`, animationDelay: delay }}>
              <div style={{ left: `${left}%`, top: "50%", animationDuration: `${duration}s`, animationDelay: delay }}>
                <i style={{ background: color }}>
                  {name
                    .split(" ")
                    .map((x) => x[0])
                    .join("")
                    .slice(0, 2)}
                </i>
                {name}
              </div>
            </div>
          ))}
          {DOT_LEFT.map((left, i) => (
            <div
              key={i}
              className="dot"
              style={{ animationDuration: `${14 + i * 5}s`, animationDelay: `-${i * 3}s`, transform: `rotate(${i * 61}deg)` }}
            >
              <span style={{ position: "absolute", left: `${left}%` }} />
            </div>
          ))}
          <div className="core">
            <img src={`${import.meta.env.BASE_URL}logo-digitalia.png`} alt="" />
            <small>DIGITALIA</small>
          </div>
        </div>
      </div>
    </div>
  );
}
