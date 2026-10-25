import { useState } from "react";
import { finance } from "./api/client";
import { useApi } from "./lib/useApi";
import { AccountingExportPage } from "./pages/AccountingExportPage";
import { ClientsProjectsPage } from "./pages/ClientsProjectsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { MonthPage } from "./pages/MonthPage";
import { RecapPage } from "./pages/RecapPage";
import { UpcomingPage } from "./pages/UpcomingPage";
import "./finance.css";

type Tab = "dash" | "month" | "expenses" | "upcoming" | "recap" | "export" | "clients";
const TABS: Array<[Tab, string]> = [
  ["dash", "Tableau de bord"],
  ["month", "Saisie du mois"],
  ["expenses", "Dépenses"],
  ["upcoming", "À venir"],
  ["recap", "Récap mensuel"],
  ["export", "Export comptable"],
  ["clients", "Clients & projets"],
];

/** Module Finance (pilotage de la facturation), monté dans l'onglet Finances réservé à l'administration. */
export function FinanceModule() {
  const [tab, setTab] = useState<Tab>("dash");
  const { data: orbitProjects } = useApi(() => finance.orbitProjects(), []);
  const { data: profiles } = useApi(() => finance.profiles(), [tab]);
  const projects = (profiles ?? []).map((p) => ({ id: p.project, name: p.project_name, client_name: p.client_name }));
  const clients = Array.from(
    new Map((profiles ?? []).map((p) => [p.client_id, { id: p.client_id, name: p.client_name }])).values(),
  );
  return (
    <div className="fin-root" data-theme="dark">
      <nav className="fin-nav" aria-label="Finance">
        {TABS.map(([k, l]) => (
          <button key={k} aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>
            {l}
          </button>
        ))}
      </nav>
      {tab === "dash" && <DashboardPage />}
      {tab === "month" && <MonthPage />}
      {tab === "expenses" && <ExpensesPage projects={projects} />}
      {tab === "upcoming" && <UpcomingPage projects={projects} />}
      {tab === "recap" && <RecapPage />}
      {tab === "export" && <AccountingExportPage clients={clients} />}
      {tab === "clients" && <ClientsProjectsPage orbitProjects={orbitProjects ?? []} />}
    </div>
  );
}
