import { useEffect, useMemo, useRef, useState } from "react";
import type { Attachment } from "../lib/types";
import { useUI } from "./UIContext";

/** Pièces jointes en attente d'envoi + enregistrement vocal (MediaRecorder). */
export function useAttachments() {
  const [files, setFiles] = useState<File[]>([]);
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const { toast } = useUI();

  const add = (list: FileList | null) => list && setFiles((f) => [...f, ...Array.from(list)]);
  const remove = (i: number) => setFiles((f) => f.filter((_, j) => j !== i));
  const clear = () => setFiles([]);

  async function toggleRecording() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    if (!navigator.mediaDevices || typeof MediaRecorder === "undefined") {
      toast("Enregistrement vocal non disponible sur ce navigateur");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const type = (rec.mimeType || "audio/webm").split(";")[0];
        const time = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }).replace(":", "h");
        setFiles((f) => [...f, new File(chunks, `Message vocal ${time}.webm`, { type })]);
        setRecording(false);
        toast("Message vocal ajouté");
      };
      rec.start();
      recorder.current = rec;
      setRecording(true);
      toast("Enregistrement… cliquez sur Arrêter quand vous avez fini");
    } catch {
      toast("Micro refusé ou indisponible");
    }
  }

  return { files, add, remove, clear, recording, toggleRecording };
}

export type AttachmentsState = ReturnType<typeof useAttachments>;

export function AttBar({ state }: { state: AttachmentsState }) {
  const input = (label: string, accept?: string, multiple = true) => (
    <label>
      {label}
      <input
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(e) => {
          state.add(e.target.files);
          e.target.value = "";
        }}
      />
    </label>
  );
  return (
    <div className="att-bar">
      {input("📷 Photo", "image/*")}
      {input("🎬 Vidéo", "video/*", false)}
      {input("🎤 Audio", "audio/*", false)}
      <button type="button" className={`rec ${state.recording ? "on" : ""}`} onClick={state.toggleRecording}>
        {state.recording ? "⏹ Arrêter" : "🎙️ Message vocal"}
      </button>
      {input("📎 Fichier")}
    </div>
  );
}

function Media({ type, url }: { type: string; url: string }) {
  if (type.startsWith("image")) return <img src={url} alt="" />;
  if (type.startsWith("video")) return <video src={url} controls />;
  if (type.startsWith("audio")) return <audio src={url} controls />;
  return <div style={{ padding: "8px 4px" }}>📎</div>;
}

/** Fichiers locaux pas encore envoyés, avec bouton « retirer ». */
export function PendingList({ state }: { state: AttachmentsState }) {
  const urls = useMemo(() => state.files.map((f) => URL.createObjectURL(f)), [state.files]);
  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)), [urls]);
  if (!state.files.length) return null;
  return (
    <div className="att-list">
      {state.files.map((f, i) => (
        <div className="att" key={urls[i]}>
          <Media type={f.type} url={urls[i]} />
          <div className="truncate" style={{ marginTop: 4, maxWidth: 200 }}>
            {f.name}
          </div>
          <button type="button" className="rm" title="Retirer" onClick={() => state.remove(i)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

/** Pièces jointes déjà enregistrées côté serveur. */
export function AttachmentList({ items }: { items: Attachment[] }) {
  if (!items.length) return null;
  return (
    <div className="att-list">
      {items.map((a) => (
        <a className="att" key={a.id} href={a.url} target="_blank" rel="noreferrer">
          <Media type={a.content_type} url={a.url} />
          <div className="truncate" style={{ marginTop: 4, maxWidth: 200 }}>
            {a.name}
          </div>
        </a>
      ))}
    </div>
  );
}
