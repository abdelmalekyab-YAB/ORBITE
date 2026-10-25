import { useState } from "react";
import { ApiError, download } from "../lib/api";
import { useUI } from "./UIContext";

/** Bouton « Exporter en CSV » (Sprint 5). */
export default function ExportButton({ path, filename }: { path: string; filename: string }) {
  const { toast } = useUI();
  const [busy, setBusy] = useState(false);
  return (
    <button
      className="btn sm"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await download(path, filename);
        } catch (e) {
          toast(e instanceof ApiError ? e.message : "Export impossible");
        } finally {
          setBusy(false);
        }
      }}
    >
      ⬇ Exporter CSV
    </button>
  );
}
