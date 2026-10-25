/* Orbit demo: runs before the React app and relays its /api and /media calls to Django running in a
   Web Worker (Pyodide). Adds a loading screen, a mailbox showing the e-mails Orbit sends, and a reset. */
(function () {
  const script = document.currentScript;
  const DEMO = new URL(".", script.src).href;            // .../ORBITE/demo/
  const BASE = new URL("..", DEMO).pathname;             // /ORBITE/
  const MEDIA_HOST = "http://orbit.demo/media/";
  const realFetch = window.fetch.bind(window);
  const worker = new Worker(DEMO + "worker.js");
  const pending = new Map();
  const blobs = new Map();
  let seq = 0, mails = [], seen = Number(localStorage.getItem("orbit.demo.seen") || 0);
  let resolveReady, rejectReady;
  const ready = new Promise((ok, ko) => { resolveReady = ok; rejectReady = ko; });

  // ---- UI -----------------------------------------------------------------
  const css = `
  .od-screen{position:fixed;inset:0;z-index:2147483000;display:grid;place-items:center;text-align:center;padding:16px;
    background:radial-gradient(1000px 520px at 85% -10%,rgba(124,58,237,.30),transparent 60%),#070511;color:#c5bde0;font:15px/1.5 Inter,system-ui,sans-serif}
  .od-screen h1{font:700 34px "Space Grotesk",Inter,system-ui,sans-serif;color:#fff;margin:0 0 8px}
  .od-meter{width:min(320px,80vw);height:6px;background:rgba(255,255,255,.12);border-radius:99px;overflow:hidden;margin:18px auto 8px}
  .od-meter i{display:block;height:100%;width:0;background:linear-gradient(95deg,#e04bff,#7c3aed);transition:width .4s}
  .od-small{font-size:12.5px;opacity:.8}
  .od-bar{position:fixed;left:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:2147482000;display:flex;gap:6px;align-items:center;
    background:rgba(16,11,32,.92);border:1px solid #2b2349;border-radius:99px;padding:5px 6px 5px 12px;font:600 12.5px Inter,system-ui,sans-serif;color:#c5bde0;box-shadow:0 6px 24px rgba(0,0,0,.4)}
  .od-bar button{font:inherit;color:#f6f3ff;background:#171130;border:1px solid #2b2349;border-radius:99px;padding:5px 11px;cursor:pointer}
  .od-bar button:hover{border-color:#a855f7}
  .od-count{display:inline-block;min-width:18px;padding:0 5px;border-radius:99px;background:#3dffb7;color:#062b1c;margin-left:4px;text-align:center}
  .od-count.zero{background:#2b2349;color:#c5bde0}
  .od-panel{position:fixed;top:0;right:0;bottom:0;width:min(460px,100%);z-index:2147482500;background:#100b20;border-left:1px solid #2b2349;
    display:flex;flex-direction:column;color:#f6f3ff;font:14px/1.5 Inter,system-ui,sans-serif;box-shadow:-10px 0 30px rgba(0,0,0,.5)}
  .od-panel header{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid #2b2349}
  .od-panel h2{margin:0;font:600 16px "Space Grotesk",Inter,sans-serif}
  .od-panel header button{background:none;border:0;color:#8b83ab;font-size:22px;cursor:pointer}
  .od-mails{overflow-y:auto;padding:12px 16px;display:grid;gap:10px;align-content:start}
  .od-mail{border:1px solid #2b2349;border-radius:12px;padding:10px 12px;background:#171130}
  .od-mail .to{font-size:12px;color:#8b83ab}.od-mail .su{font-weight:700;margin:2px 0 6px}
  .od-mail pre{white-space:pre-wrap;word-wrap:break-word;font:inherit;font-size:13px;margin:0;color:#c5bde0}
  .od-mail a{color:#d8b4fe;font-weight:600}
  .od-empty{color:#8b83ab}
  [hidden]{display:none!important}`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);

  const screen = document.createElement("div");
  screen.className = "od-screen";
  screen.innerHTML = `<div><h1>◎ Orbit</h1><p>Chargement de l'application complète dans votre navigateur…</p>
    <div class="od-meter"><i></i></div><div class="od-small" data-step>Démarrage</div>
    <p class="od-small">Démo : données fictives, gardées sur cet appareil. Le premier chargement prend quelques secondes.</p></div>`;
  const STEPS = { python: "Démarrage de Python", packages: "Chargement de Django", app: "Chargement d'Orbit", django: "Préparation des données", ready: "Prêt" };

  const bar = document.createElement("div");
  bar.className = "od-bar"; bar.setAttribute("role", "region"); bar.setAttribute("aria-label", "Démo");
  bar.innerHTML = `<span>Démo</span><button type="button" data-accounts>👤 Comptes</button><button type="button" data-mails>📬 E-mails <span class="od-count zero" data-count>0</span></button>
    <button type="button" data-reset title="Remettre les données de départ">↺ Réinitialiser</button>`;
  const panel = document.createElement("aside");
  panel.className = "od-panel"; panel.hidden = true; panel.setAttribute("aria-label", "E-mails envoyés");
  panel.innerHTML = `<header><h2>📬 E-mails envoyés par Orbit</h2><button type="button" aria-label="Fermer" data-close>×</button></header><div class="od-mails" data-list></div>`;

  const ACCOUNTS = [
    ["admin@digitalia.io", "Yasmina A.", "Digitalia · administratrice (tout, dont finances et accès)"],
    ["yanis@digitalia.io", "Yanis", "Digitalia · chef de projet (triage, réglages)"],
    ["sara@digitalia.io", "Sara", "Digitalia · développeuse"],
    ["julie@wws.fr", "Julie Martin", "Client WWS · 2 projets"],
    ["marc@rmclub.fr", "Marc Leroy", "Client RM Club"],
    ["nadia@bodytime.ma", "Nadia Benali", "Client Bodytime"],
  ];
  const accounts = document.createElement("aside");
  accounts.className = "od-panel"; accounts.hidden = true; accounts.setAttribute("aria-label", "Comptes de démonstration");
  accounts.innerHTML = `<header><h2>👤 Comptes de démonstration</h2><button type="button" aria-label="Fermer" data-close>×</button></header>
    <div class="od-mails"><p class="od-empty">Mot de passe pour tous : <b style="color:#fff">orbit</b>. Cliquez sur un compte pour vous connecter avec.</p>
    ${ACCOUNTS.map(([email, name, role]) => `<button type="button" class="od-mail od-account" data-email="${email}" style="text-align:left;cursor:pointer;color:inherit;font:inherit">
      <div class="su">${name}</div><div class="to">${email}</div><div class="to">${role}</div></button>`).join("")}</div>`;
  function setValue(input, value) {
    // React tracks input values: use the native setter, then announce the change.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
  async function signIn(email) {
    accounts.hidden = true;
    if (localStorage.getItem("orbit.access")) {
      // Someone is logged in: start again from a clean page, then log in (see the end of this file).
      ["orbit.access", "orbit.refresh"].forEach((k) => localStorage.removeItem(k));
      sessionStorage.setItem("orbit.demo.signin", email);
      location.href = BASE;
      return;
    }
    if (!location.pathname.endsWith("/login")) {
      history.pushState({}, "", BASE + "login"); dispatchEvent(new PopStateEvent("popstate"));
    }
    for (let i = 0; i < 40 && !document.querySelector('input[type="password"]'); i++) await new Promise((r) => setTimeout(r, 100));
    const mail = document.querySelector('input[type="email"]'), pass = document.querySelector('input[type="password"]');
    if (!mail || !pass) return;
    setValue(mail, email); setValue(pass, "orbit");
    pass.form && pass.form.requestSubmit();
  }
  accounts.addEventListener("click", (e) => {
    const b = e.target.closest("[data-email]"); if (b) signIn(b.dataset.email);
    if (e.target.closest("[data-close]")) accounts.hidden = true;
  });

  function mount() { document.body.append(screen, bar, panel, accounts); }
  document.body ? mount() : document.addEventListener("DOMContentLoaded", mount);

  function goTo(url) {
    const u = new URL(url, location.href);
    if (u.origin !== location.origin || !u.pathname.startsWith(BASE)) { window.open(url, "_blank", "noopener"); return; }
    history.pushState({}, "", u.pathname + u.search);
    dispatchEvent(new PopStateEvent("popstate"));
  }
  function renderCount() {
    const c = bar.querySelector("[data-count]"), unread = mails.length - seen;
    c.textContent = unread > 0 ? unread : mails.length; c.classList.toggle("zero", unread <= 0);
  }
  function renderMails() {
    const list = panel.querySelector("[data-list]"); list.innerHTML = "";
    if (!mails.length) { list.innerHTML = '<p class="od-empty">Aucun e-mail pour l\'instant. Invitez un utilisateur depuis Accès, demandez un nouveau mot de passe ou faites avancer un ticket : les e-mails apparaîtront ici.</p>'; return; }
    mails.slice().reverse().forEach((m) => {
      const div = document.createElement("div"); div.className = "od-mail";
      const to = document.createElement("div"); to.className = "to"; to.textContent = "À : " + m.to.join(", ");
      const su = document.createElement("div"); su.className = "su"; su.textContent = m.subject;
      const pre = document.createElement("pre");
      m.body.split(/(https?:\/\/\S+)/).forEach((part) => {
        if (/^https?:\/\//.test(part)) {
          const a = document.createElement("a"); a.href = part; a.textContent = part;
          a.addEventListener("click", (e) => { e.preventDefault(); panel.hidden = true; goTo(part); });
          pre.appendChild(a);
        } else pre.appendChild(document.createTextNode(part));
      });
      div.append(to, su, pre); list.appendChild(div);
    });
  }
  bar.querySelector("[data-accounts]").addEventListener("click", () => { panel.hidden = true; accounts.hidden = !accounts.hidden; });
  bar.querySelector("[data-mails]").addEventListener("click", () => {
    accounts.hidden = true;
    panel.hidden = !panel.hidden; seen = mails.length; localStorage.setItem("orbit.demo.seen", String(seen)); renderMails(); renderCount();
  });
  panel.querySelector("[data-close]").addEventListener("click", () => { panel.hidden = true; });
  bar.querySelector("[data-reset]").addEventListener("click", async () => {
    await ready; await call({ kind: "reset" });
    ["orbit.access", "orbit.refresh", "orbit.demo.seen"].forEach((k) => localStorage.removeItem(k));
    location.href = BASE;
  });

  // ---- Worker ---------------------------------------------------------------
  function call(message) {
    return new Promise((resolve, reject) => {
      const id = ++seq; pending.set(id, { resolve, reject }); worker.postMessage(Object.assign({ id }, message));
    });
  }
  worker.onerror = (e) => rejectReady(new Error(e.message || "Le moteur de la démo n'a pas pu démarrer."));
  worker.onmessage = ({ data }) => {
    if (data.type === "progress") {
      screen.querySelector(".od-meter i").style.width = data.pct + "%";
      screen.querySelector("[data-step]").textContent = STEPS[data.step] || data.step; return;
    }
    if (data.type === "ready") { screen.remove(); resolveReady(); return; }
    if (data.type === "failed") { rejectReady(new Error(data.error)); return; }
    const p = pending.get(data.id); if (!p) return; pending.delete(data.id);
    data.ok ? p.resolve(data.response) : p.reject(new Error(data.error));
  };
  ready.then(() => {
    const email = sessionStorage.getItem("orbit.demo.signin");
    if (email) { sessionStorage.removeItem("orbit.demo.signin"); setTimeout(() => signIn(email), 300); }
  });
  ready.catch((err) => {
    console.error("Orbit demo failed to start:", err.message || err);
    screen.querySelector("p").textContent = "Ce navigateur n'a pas pu démarrer la démo d'Orbit.";
    screen.querySelector("[data-step]").textContent = String(err.message || err).slice(0, 400);
  });

  async function mediaBlob(url) {
    if (!blobs.has(url)) {
      const res = await call({ kind: "request", request: { method: "GET", path: "/media/" + url.slice(MEDIA_HOST.length) } });
      blobs.set(url, URL.createObjectURL(new Blob([res.body], { type: (res.contentType || "").split(";")[0] })));
    }
    return blobs.get(url);
  }

  async function demoFetch(request) {
    await ready;
    const url = new URL(request.url);
    const body = ["GET", "HEAD"].includes(request.method) ? null : new Uint8Array(await request.arrayBuffer());
    const res = await call({ kind: "request", request: {
      method: request.method, path: "/" + url.pathname.slice(BASE.length) + url.search, body,
      contentType: request.headers.get("content-type") || "", authorization: request.headers.get("authorization") || "",
    } });
    if (res.status >= 500) console.error("Orbit demo: server error on", request.method, url.pathname, new TextDecoder().decode(res.body).slice(-600));
    if (res.mails) { mails = res.mails; renderCount(); if (!panel.hidden) renderMails(); }
    let payload = res.body;
    // Attachments are served by the in-browser Django: turn their URLs into blob URLs the page can load.
    if ((res.contentType || "").includes("json")) {
      let text = new TextDecoder().decode(res.body);
      const urls = [...new Set(text.match(/http:\/\/orbit\.demo\/media\/[^"\\]+/g) || [])];
      for (const u of urls) text = text.split(u).join(await mediaBlob(u));
      payload = text;
    }
    const headers = { "Content-Type": res.contentType || "application/octet-stream" };
    if (res.disposition) headers["Content-Disposition"] = res.disposition;
    return new Response(payload, { status: res.status, headers });
  }

  window.fetch = function (input, init) {
    const request = new Request(input, init);
    const path = new URL(request.url).pathname;
    if (new URL(request.url).origin === location.origin && (path.startsWith(BASE + "api/") || path.startsWith(BASE + "media/"))) {
      return demoFetch(request);
    }
    return realFetch(input, init);
  };
})();
