/* Orbit: Kanban drag & drop, client actions and the "not OK" explanation dialog. */
(function () {
  const i18n = window.ORBIT_I18N || {};
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const toast = document.getElementById("board-toast");
  const NEEDS_EXPLANATION = ["test_ko", "reopen"];

  function say(msg, bad) {
    if (!toast) return;
    toast.textContent = msg; toast.classList.toggle("bad", !!bad); toast.hidden = false;
    clearTimeout(say.t); say.t = setTimeout(() => { toast.hidden = true; }, 3500);
  }
  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, body: JSON.stringify(body) })
      .then(r => r.json().then(data => { if (!r.ok) { const e = new Error(data.error || ""); e.data = data; throw e; } return data; }));
  }

  // "What is not working?" dialog. Resolves with the text, or null if cancelled.
  const dialog = document.getElementById("explain-dialog");
  function askExplanation() {
    return new Promise(resolve => {
      const text = document.getElementById("explain-text"), err = document.getElementById("explain-error");
      const form = document.getElementById("explain-form"), cancel = document.getElementById("explain-cancel");
      text.value = ""; err.hidden = true;
      const done = value => { form.onsubmit = null; cancel.onclick = null; dialog.onclose = null; if (dialog.open) dialog.close(); resolve(value); };
      form.onsubmit = e => {
        e.preventDefault();
        if (text.value.trim().length < 10) { err.textContent = i18n.tooShort; err.hidden = false; text.focus(); return; }
        done(text.value.trim());
      };
      cancel.onclick = () => done(null);
      dialog.onclose = () => done(null);
      dialog.showModal(); text.focus();
    });
  }

  async function clientAct(url, body, ref) {
    if (NEEDS_EXPLANATION.includes(body.action)) {
      const message = await askExplanation();
      if (message === null) return false;
      body.message = message;
    }
    try {
      const data = await post(url, body);
      say((ref ? ref + " : " : "") + data.label);
      setTimeout(() => location.reload(), 900);
      return true;
    } catch (err) {
      if (err.data && err.data.needs_message && !body.message) {
        // A drop that means "not OK": ask for the explanation, then send again.
        const message = await askExplanation();
        if (message === null) return false;
        return clientAct(url, Object.assign({}, body, { message }), ref);
      }
      say(err.message || i18n.saveError, true);
      return false;
    }
  }

  // Buttons: I answered / Test OK / Not OK / Not OK after all.
  document.querySelectorAll("[data-action]").forEach(btn => btn.addEventListener("click", async e => {
    e.preventDefault();
    const holder = btn.closest("[data-move-url]");
    btn.disabled = true;
    const ok = await clientAct(holder.dataset.moveUrl, { action: btn.dataset.action }, holder.dataset.ref);
    if (!ok) btn.disabled = false;
  }));

  // Drag & drop.
  let dragged = null;
  function refreshEmpty(col) {
    const empty = col.querySelector(".col-empty"), hasCards = col.querySelector(".kcard");
    if (hasCards && empty) empty.remove();
    if (!hasCards && !empty) { const d = document.createElement("div"); d.className = "col-empty"; d.textContent = "—"; col.appendChild(d); }
  }
  function recount() {
    document.querySelectorAll("[data-count-for]").forEach(el => {
      el.textContent = document.querySelectorAll('.col[data-status="' + el.dataset.countFor + '"] .kcard').length;
    });
  }
  document.querySelectorAll(".kcard[draggable=true]").forEach(card => {
    card.addEventListener("dragstart", e => {
      dragged = card; card.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", card.dataset.id);
      if (card.dataset.client) document.querySelectorAll(".col").forEach(c => { if (c !== card.parentElement) c.classList.add("can-drop"); });
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging"); dragged = null;
      document.querySelectorAll(".col.over, .col.can-drop").forEach(c => c.classList.remove("over", "can-drop"));
    });
  });
  document.querySelectorAll(".col").forEach(col => {
    col.addEventListener("dragover", e => { if (!dragged) return; e.preventDefault(); col.classList.add("over"); });
    col.addEventListener("dragleave", e => { if (!col.contains(e.relatedTarget)) col.classList.remove("over"); });
    col.addEventListener("drop", async e => {
      e.preventDefault(); col.classList.remove("over");
      if (!dragged) return;
      const card = dragged, from = card.parentElement, target = col.dataset.status;
      if (from === col) return;
      if (from.parentElement !== col.parentElement) { say(i18n.moveRow, true); return; }
      if (card.dataset.client) { await clientAct(card.dataset.moveUrl, { column: target }, card.dataset.ref); return; }
      col.appendChild(card); refreshEmpty(col); refreshEmpty(from); recount();
      try { const data = await post(card.dataset.moveUrl, { status: target }); card.dataset.status = data.status; say(card.dataset.ref + " → " + data.label); }
      catch (err) { from.appendChild(card); refreshEmpty(col); refreshEmpty(from); recount(); say(i18n.saveError, true); }
    });
  });

  document.querySelectorAll("#board-filters select, #board-filters input[type=checkbox]").forEach(el => el.addEventListener("change", () => el.form.submit()));
})();
