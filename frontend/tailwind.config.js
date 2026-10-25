/** Tokens de design Orbit — voir docs/06-ecrans.md */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { bg: "#070511", s1: "#100b20", s2: "#171130", s3: "#1f1840", ink: "#f6f3ff", ink2: "#c5bde0",
      mute: "#8b83ab", line: "#2b2349", line2: "#211a3c", violet: "#a855f7", neon: "#3dffb7", amber: "#ffc14d",
      rose: "#ff6b8a", cyan: "#3de1ff", magenta: "#e04bff" },
    fontFamily: { display: ["Space Grotesk", "Inter", "sans-serif"], body: ["Inter", "system-ui", "sans-serif"] },
    backgroundImage: { grad: "linear-gradient(95deg,#e04bff 0%,#a21caf 45%,#7c3aed 100%)" },
    borderRadius: { card: "18px", pill: "99px" },
  } },
  plugins: [],
  // `.ring` est un composant de la maquette (anneau d'avancement) : on retire l'utilitaire Tailwind homonyme.
  corePlugins: { ringWidth: false },
};
