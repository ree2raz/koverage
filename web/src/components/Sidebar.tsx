import { NavLink, useNavigate, useParams } from "react-router-dom";
import { useStore } from "../store";

const navItem =
  "px-3 py-1.5 rounded-md text-sm font-medium transition-colors";

function statusDot(status: string) {
  const color =
    status === "cancelled" ? "bg-amber-400" : status === "archived" ? "bg-slate-500" : "bg-emerald-400";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} />;
}

export default function Sidebar() {
  const { conversations } = useStore();
  const { id } = useParams();
  const navigate = useNavigate();

  return (
    <aside className="w-72 shrink-0 border-r border-slate-800 bg-[#0e131c] flex flex-col">
      <div className="px-4 py-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-lg">🛰️</span>
          <span className="font-semibold tracking-tight">Beacon</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-0.5">LLM observability + evaluation</p>
      </div>

      <nav className="flex gap-1 px-3 py-2 border-b border-slate-800">
        {[
          ["/", "Chat"],
          ["/observability", "Observability"],
          ["/evaluation", "Evaluation"],
        ].map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `${navItem} ${isActive ? "bg-slate-700/60 text-white" : "text-slate-400 hover:text-white"}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-2">
        <button
          onClick={() => navigate("/")}
          className="w-full rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
        >
          + New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <p className="px-2 py-1 text-[11px] uppercase tracking-wide text-slate-600">Conversations</p>
        {conversations.length === 0 && (
          <p className="px-2 py-2 text-xs text-slate-600">No conversations yet.</p>
        )}
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => navigate(`/c/${c.id}`)}
            className={`w-full text-left rounded-md px-2 py-2 text-sm truncate flex items-center gap-2 ${
              id === c.id ? "bg-slate-700/50 text-white" : "text-slate-300 hover:bg-slate-800/60"
            }`}
            title={c.title}
          >
            {statusDot(c.status)}
            <span className="truncate">{c.title || "Untitled"}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}
