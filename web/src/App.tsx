import { useLocation } from "react-router-dom";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ChatView from "./components/ChatView";
import Dashboard from "./components/Dashboard";
import EvaluationView from "./components/EvaluationView";
import { StoreProvider } from "./store";

const NAV = [
  { to: "/", label: "Chat", end: true },
  { to: "/observability", label: "Observability", end: false },
  { to: "/evaluation", label: "Evaluation", end: false },
];

function TopBar() {
  return (
    <header className="flex items-center gap-5 px-4 h-11 border-b border-slate-800 bg-slate-900 shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-sm">🛰️</span>
        <span className="font-semibold text-sm tracking-tight text-white">Beacon</span>
      </div>
      <nav className="flex gap-0.5">
        {NAV.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                isActive
                  ? "bg-slate-700/60 text-white"
                  : "text-slate-400 hover:text-white"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}

export default function App() {
  const location = useLocation();
  const isChat = location.pathname === "/" || location.pathname.startsWith("/c/");

  return (
    <StoreProvider>
      <div className="flex flex-col h-screen w-screen overflow-hidden">
        <TopBar />
        <div className="flex flex-1 min-h-0">
          {isChat && <Sidebar />}
          <main className="flex-1 min-w-0 flex flex-col">
            <Routes>
              <Route path="/" element={<ChatView />} />
              <Route path="/c/:id" element={<ChatView />} />
              <Route path="/observability" element={<Dashboard />} />
              <Route path="/evaluation" element={<EvaluationView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </StoreProvider>
  );
}
