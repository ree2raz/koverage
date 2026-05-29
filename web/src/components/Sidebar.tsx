import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useStore } from "../store";

const navItem = "px-3 py-1.5 rounded-md text-sm font-medium transition-colors";

function statusDot(status: string) {
  const color =
    status === "cancelled" ? "bg-amber-400" : status === "archived" ? "bg-slate-500" : "bg-emerald-400";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${color}`} />;
}

export default function Sidebar() {
  const { conversations, refresh } = useStore();
  const location = useLocation();
  const activeId = location.pathname.match(/^\/c\/(.+)$/)?.[1];
  const navigate = useNavigate();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) inputRef.current.focus();
  }, [editingId]);

  function startRename(id: string, currentTitle: string) {
    setEditingId(id);
    setEditTitle(currentTitle || "");
  }

  async function commitRename(id: string) {
    const title = editTitle.trim();
    setEditingId(null);
    if (title) {
      await api.renameConversation(id, title);
      refresh();
    }
  }

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    await api.deleteConversation(id);
    refresh();
    if (activeId === id) navigate("/");
  }

  return (
    <aside className="w-72 shrink-0 border-r border-slate-800 bg-slate-900 flex flex-col">
      <div className="px-4 py-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-lg">🛰️</span>
          <span className="font-semibold tracking-tight">Beacon</span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">LLM observability + evaluation</p>
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
        <p className="px-2 py-1 text-xs uppercase tracking-wide text-slate-400">Conversations</p>
        {conversations.length === 0 && (
          <p className="px-2 py-2 text-xs text-slate-400">No conversations yet.</p>
        )}
        {conversations.map((c) => {
          const isActive = activeId === c.id;
          const isEditing = editingId === c.id;

          return (
            <div
              key={c.id}
              className={`group relative flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-indigo-600/30 border border-indigo-500/50 text-white"
                  : "text-slate-300 hover:bg-slate-800/60 border border-transparent"
              }`}
            >
              {statusDot(c.status)}

              {isEditing ? (
                <input
                  ref={inputRef}
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onBlur={() => commitRename(c.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename(c.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  className="flex-1 min-w-0 bg-slate-800 border border-indigo-500 rounded px-1.5 py-0.5 text-sm text-white outline-none"
                />
              ) : (
                <button
                  onClick={() => navigate(`/c/${c.id}`)}
                  className="flex-1 min-w-0 text-left truncate"
                  title={c.title}
                >
                  {c.title || "Untitled"}
                </button>
              )}

              {!isEditing && (
                <div className={`flex gap-0.5 shrink-0 transition-opacity ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
                  <button
                    onClick={(e) => { e.stopPropagation(); startRename(c.id, c.title); }}
                    title="Rename"
                    className="rounded p-1 hover:bg-slate-700 text-slate-400 hover:text-slate-200"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                  <button
                    onClick={(e) => handleDelete(e, c.id)}
                    title="Delete"
                    className="rounded p-1 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                      <path d="M10 11v6M14 11v6"/>
                      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                    </svg>
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
