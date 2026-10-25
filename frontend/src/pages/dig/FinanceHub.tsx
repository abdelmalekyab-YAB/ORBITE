import { useState } from "react";
import { FinanceModule } from "../../finance/FinanceModule";
import Finance from "./Finance";

/** Onglet Finances (admin) : pilotage de la facturation + vue rentabilité par projet. */
export default function FinanceHub() {
  const [view, setView] = useState<"billing" | "projects">("billing");
  return (
    <>
      <div className="toolbar" role="tablist" aria-label="Finances">
        <button className={`btn sm${view === "billing" ? " grad" : " ghost"}`} onClick={() => setView("billing")}>
          Facturation
        </button>
        <button className={`btn sm${view === "projects" ? " grad" : " ghost"}`} onClick={() => setView("projects")}>
          Rentabilité par projet
        </button>
      </div>
      {view === "billing" ? <FinanceModule /> : <Finance />}
    </>
  );
}
