import { useState } from "react";
import type { ChatMessage } from "../types";

function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-1 py-0.5">
      <span className="typing-dot" />
      <span className="typing-dot" style={{ animationDelay: "0.18s" }} />
      <span className="typing-dot" style={{ animationDelay: "0.36s" }} />
    </span>
  );
}

// Reasoning models (e.g. self-hosted Qwen3) emit chain-of-thought wrapped in
// <think>…</think>. Split it out so the reasoning never renders as the answer.
// Handles the streaming case where the closing tag hasn't arrived yet.
function parseThinking(content: string): {
  answer: string;
  reasoning: string;
  thinking: boolean;
} {
  const OPEN = "<think>";
  const CLOSE = "</think>";
  let rest = content;
  let answer = "";
  let reasoning = "";
  let thinking = false;

  while (rest.length > 0) {
    const open = rest.indexOf(OPEN);
    if (open === -1) {
      answer += rest;
      break;
    }
    answer += rest.slice(0, open);
    const after = rest.slice(open + OPEN.length);
    const close = after.indexOf(CLOSE);
    if (close === -1) {
      // open block still streaming — everything after is in-progress reasoning
      reasoning += after;
      thinking = true;
      break;
    }
    reasoning += after.slice(0, close);
    rest = after.slice(close + CLOSE.length);
  }

  return { answer: answer.trim(), reasoning: reasoning.trim(), thinking };
}

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [showReasoning, setShowReasoning] = useState(false);

  const { answer, reasoning, thinking } = isUser
    ? { answer: message.content, reasoning: "", thinking: false }
    : parseThinking(message.content);

  // pending = nothing visible yet (no answer, no reasoning) while streaming
  const isPending = message.streaming && !answer && !reasoning;
  // still inside a <think> block with no answer yet → show a "Reasoning…" hint
  const reasoningOnly = message.streaming && thinking && !answer;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
          isUser
            ? "bg-indigo-600 text-white rounded-br-sm"
            : "bg-slate-800 text-slate-100 rounded-bl-sm"
        }`}
      >
        {isPending ? (
          <TypingIndicator />
        ) : (
          <>
            {/* collapsible chain-of-thought (assistant only) */}
            {reasoning && (
              <div className="mb-2">
                <button
                  onClick={() => setShowReasoning((v) => !v)}
                  className="text-xs text-slate-400 hover:text-slate-200 inline-flex items-center gap-1"
                >
                  <span>{showReasoning ? "▾" : "▸"}</span>
                  <span>{thinking && !answer ? "Reasoning…" : "Reasoning"}</span>
                </button>
                {showReasoning && (
                  <div className="mt-1 border-l-2 border-slate-600 pl-2 text-xs text-slate-400 whitespace-pre-wrap">
                    {reasoning}
                  </div>
                )}
              </div>
            )}

            {reasoningOnly ? (
              <TypingIndicator />
            ) : (
              <>
                {answer}
                {message.streaming && (
                  <span className="inline-block w-[3px] h-[14px] ml-0.5 align-middle bg-slate-400 rounded-sm animate-pulse" />
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
