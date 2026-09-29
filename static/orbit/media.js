/* Orbit: attach photos, videos, voice recordings and documents to a form. */
(function () {
  const T = window.ORBIT_I18N || {};
  const ICON = { image: "🖼️", video: "🎬", audio: "🎙️", document: "📄" };
  const KINDS = {
    image: /\.(png|jpe?g|gif|webp|heic|heif|bmp|svg)$/i, video: /\.(mp4|webm|mov|m4v|ogv|avi|mkv|3gp)$/i,
    audio: /\.(mp3|wav|ogg|oga|opus|m4a|aac|weba|flac|amr)$/i,
  };
  const kindOf = f => Object.keys(KINDS).find(k => KINDS[k].test(f.name)) || (f.type.split("/")[0] in ICON ? f.type.split("/")[0] : "document");
  const size = n => n > 1048576 ? (n / 1048576).toFixed(1) + " Mo" : Math.max(1, Math.round(n / 1024)) + " Ko";

  function setup(root) {
    const store = root.querySelector("[data-media-store]"), list = root.querySelector("[data-media-list]");
    const error = root.querySelector("[data-media-error]");
    let files = [];

    function sync() {
      const dt = new DataTransfer();
      files.forEach(f => dt.items.add(f));
      store.files = dt.files;
      list.innerHTML = "";
      files.forEach((f, i) => {
        const li = document.createElement("li"), kind = kindOf(f);
        li.className = "media-item";
        let preview = "";
        if (kind === "image") preview = `<img alt="" src="${URL.createObjectURL(f)}">`;
        else if (kind === "audio") preview = `<audio controls src="${URL.createObjectURL(f)}"></audio>`;
        else if (kind === "video") preview = `<video controls muted src="${URL.createObjectURL(f)}"></video>`;
        li.innerHTML = `<span class="media-icon">${ICON[kind]}</span><span class="media-name"></span><span class="muted">${size(f.size)}</span>${preview}<button type="button" class="media-remove" aria-label="${T.remove || "Remove"}">×</button>`;
        li.querySelector(".media-name").textContent = f.name;
        li.querySelector(".media-remove").onclick = () => { files.splice(i, 1); sync(); };
        list.appendChild(li);
      });
      root.dispatchEvent(new CustomEvent("media-change", { bubbles: true, detail: { count: files.length } }));
    }
    function add(newFiles) { files = files.concat(Array.from(newFiles)); error.hidden = true; sync(); }
    root.orbitFiles = () => files.slice();
    root.orbitReset = () => { files = []; sync(); };

    root.querySelectorAll("[data-media-pick]").forEach(input => input.addEventListener("change", () => { add(input.files); input.value = ""; }));
    root.addEventListener("dragover", e => { e.preventDefault(); root.classList.add("drop"); });
    root.addEventListener("dragleave", () => root.classList.remove("drop"));
    root.addEventListener("drop", e => { e.preventDefault(); root.classList.remove("drop"); if (e.dataTransfer.files.length) add(e.dataTransfer.files); });

    // Voice recording.
    const recBtn = root.querySelector("[data-media-record]"), recBox = root.querySelector("[data-media-recording]");
    const timer = root.querySelector("[data-media-timer]");
    let recorder = null, chunks = [], started = 0, tick = null, keep = false;
    if (!window.MediaRecorder || !navigator.mediaDevices) recBtn.hidden = true;
    recBtn.addEventListener("click", async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const type = ["audio/webm", "audio/mp4", "audio/ogg"].find(t => MediaRecorder.isTypeSupported(t)) || "";
        recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
        chunks = []; keep = false;
        recorder.ondataavailable = e => e.data.size && chunks.push(e.data);
        recorder.onstop = () => {
          stream.getTracks().forEach(t => t.stop()); clearInterval(tick); recBox.hidden = true; recBtn.hidden = false;
          if (!keep || !chunks.length) return;
          const mime = recorder.mimeType || "audio/webm", ext = mime.includes("mp4") ? "m4a" : mime.includes("ogg") ? "oga" : "weba";
          const stamp = new Date().toISOString().slice(0, 16).replace("T", " ").replace(":", "h");
          add([new File(chunks, `${T.voiceNote || "Note vocale"} ${stamp}.${ext}`, { type: mime })]);
        };
        recorder.start(); started = Date.now(); recBox.hidden = false; recBtn.hidden = true;
        tick = setInterval(() => { const s = Math.floor((Date.now() - started) / 1000); timer.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }, 250);
      } catch (err) {
        error.textContent = T.micDenied || "Microphone unavailable."; error.hidden = false;
      }
    });
    root.querySelector("[data-media-stop]").addEventListener("click", () => { keep = true; recorder && recorder.stop(); });
    root.querySelector("[data-media-cancel]").addEventListener("click", () => { keep = false; recorder && recorder.stop(); });
  }
  window.orbitSetupMedia = el => { if (!el.orbitFiles) setup(el); };
  document.querySelectorAll("[data-media-input]").forEach(el => window.orbitSetupMedia(el));
})();
