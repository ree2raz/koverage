import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api/client";
import type { ConversationSummary } from "./types";

interface Store {
  conversations: ConversationSummary[];
  refresh: () => void;
  sessionId: string;
}

const Ctx = createContext<Store | null>(null);

// A stable per-browser session id so conversations can be grouped if we want to.
function getSessionId(): string {
  let id = localStorage.getItem("beacon.session");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("beacon.session", id);
  }
  return id;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const sessionId = getSessionId();

  const refresh = useCallback(() => {
    api.conversations().then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return <Ctx.Provider value={{ conversations, refresh, sessionId }}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used within StoreProvider");
  return ctx;
}
