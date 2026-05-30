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

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isPending = message.streaming && !message.content;

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
            {message.content}
            {message.streaming && (
              <span className="inline-block w-[3px] h-[14px] ml-0.5 align-middle bg-slate-400 rounded-sm animate-pulse" />
            )}
          </>
        )}
      </div>
    </div>
  );
}
