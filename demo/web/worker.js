/* Runs Orbit's Django API in the browser with Pyodide; the page talks to it with messages. */
importScripts("pyodide/pyodide.js");

const here = (p) => new URL(p, self.location).href;
let py = null, handle = null, stage = "start", persistent = false;
const progress = (step, pct) => { stage = step; postMessage({ type: "progress", step, pct }); };
function describe(err) {
  if (!err) return "unknown error";
  const parts = [err.name, err.message, err.errno != null && "errno " + err.errno].filter(Boolean);
  return `[${stage}] ` + (parts.join(" · ") || JSON.stringify(err)) + (err.stack ? "\n" + String(err.stack).slice(0, 1500) : "");
}
// Saving to IndexedDB is a convenience: when the browser refuses it, the demo runs in memory.
const syncfs = (populate) => !persistent ? Promise.resolve() :
  new Promise((ok) => py.FS.syncfs(populate, (err) => { if (err) persistent = false; ok(); }));
const bytes = async (path) => new Uint8Array(await (await fetch(here(path))).arrayBuffer());

async function boot() {
  progress("python", 5);
  py = await loadPyodide({ indexURL: here("pyodide/") });
  progress("packages", 30);
  await py.loadPackage(["sqlite3", "ssl", "pillow"]);
  const wheels = await (await fetch(here("wheels.json"))).json();
  await py.loadPackage(wheels.map(here));
  progress("app", 70);
  py.unpackArchive(await bytes("app.zip"), "zip", { extractDir: "/app" });
  py.FS.mkdirTree("/data");
  try {
    if (typeof indexedDB === "undefined") throw new Error("no IndexedDB");
    py.FS.mount(py.FS.filesystems.IDBFS, {}, "/data");
    persistent = true;
    await syncfs(true);
  } catch (e) { persistent = false; }
  let fresh = false;
  try { py.FS.stat("/data/db.sqlite3"); } catch (e) { fresh = true; }
  if (fresh) { py.unpackArchive(await bytes("seed.zip"), "zip", { extractDir: "/data" }); await syncfs(false); }
  progress("django", 85);
  await py.runPythonAsync(await (await fetch(here("boot.py"))).text());
  handle = py.globals.get("handle");
  progress("ready", 100);
}

const booting = boot().then(
  () => postMessage({ type: "ready", persistent }),
  (err) => postMessage({ type: "failed", error: describe(err) }),
);

onmessage = async ({ data }) => {
  const { id } = data;
  try {
    await booting;
    if (!handle) throw new Error("Orbit did not start");
    if (data.kind === "reset") {
      py.runPython("reset_demo()");
      py.unpackArchive(await bytes("seed.zip"), "zip", { extractDir: "/data" });
      await syncfs(false);
      postMessage({ id, ok: true });
      return;
    }
    const result = handle(py.toPy(data.request)).toJs({ dict_converter: Object.fromEntries });
    if (data.request.method !== "GET") await syncfs(false);
    postMessage({ id, ok: true, response: result }, result.body && result.body.buffer ? [result.body.buffer] : []);
  } catch (err) {
    postMessage({ id, ok: false, error: describe(err) });
  }
};
