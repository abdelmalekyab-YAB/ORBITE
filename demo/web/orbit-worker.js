/* Runs Orbit (Django) inside the browser with Pyodide. The page talks to it with messages. */
importScripts("pyodide/pyodide.js");

const here = p => new URL(p, self.location).href;
let py = null, handle = null;
const progress = (step, pct) => postMessage({ type: "progress", step, pct });
// Archives are published as base64 text (pages may not serve .zip or .whl files).
async function fetchBytes(path) {
  const text = await (await fetch(here(path + ".b64.txt"))).text();
  const bin = atob(text), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
const syncfs = populate => new Promise((ok, ko) => py.FS.syncfs(populate, err => err ? ko(err) : ok()));

async function unpackSeed() {
  py.unpackArchive(await fetchBytes("orbit-data.zip"), "zip", { extractDir: "/data" });
}

async function boot() {
  progress("python", 5);
  const stdlib = URL.createObjectURL(new Blob([await fetchBytes("pyodide/python_stdlib.zip")]));
  py = await loadPyodide({ indexURL: here("pyodide/"), stdLibURL: stdlib });
  progress("packages", 35);
  const wheels = await (await fetch(here("wheels.json"))).json();
  // Wheels are plain archives: unpack them into site-packages (_sqlite3.so is loaded on import).
  for (const wheel of wheels) py.unpackArchive(await fetchBytes(wheel), "wheel");
  progress("app", 70);
  py.unpackArchive(await fetchBytes("orbit-app.zip"), "zip", { extractDir: "/app" });
  py.FS.mkdirTree("/data");
  try {
    if (typeof indexedDB === "undefined") throw new Error("no IndexedDB");
    py.FS.mount(py.FS.filesystems.IDBFS, {}, "/data");
    persistent = true;
    await syncfs(true);
  } catch (e) { persistent = false; }
  if (!persistent) { try { py.FS.unmount("/data"); } catch (e) {} py.FS.mkdirTree("/data"); }
  let fresh = false;
  try { py.FS.stat("/data/db.sqlite3"); } catch (e) { fresh = true; }
  if (fresh) { await unpackSeed(); await syncfs(false); }
  progress("django", 85);
  const boot = await (await fetch(here("orbit-boot.py"))).text();
  await py.runPythonAsync(boot);
  handle = py.globals.get("handle");
  progress("ready", 100);
}

const booting = boot().then(
  () => postMessage({ type: "ready", persistent }),
  err => postMessage({ type: "failed", error: describe(err) }),
);

onmessage = async ({ data }) => {
  const { id } = data;
  try {
    await booting;
    if (!handle) throw new Error("Orbit did not start");
    if (data.kind === "reset") {
      py.runPython("reset_demo()");
      await unpackSeed();
      await syncfs(false);
      postMessage({ id, ok: true });
      return;
    }
    const result = handle(py.toPy(data.request)).toJs({ dict_converter: Object.fromEntries });
    if (data.request.method !== "GET" || result.changed) await syncfs(false);
    const body = result.body;
    postMessage({ id, ok: true, response: result }, body && body.buffer ? [body.buffer] : []);
  } catch (err) {
    postMessage({ id, ok: false, error: describe(err) });
  }
};
