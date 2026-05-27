import type { ChatMessage } from "../types";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
          isUser
            ? "bg-indigo-600 text-white rounded-br-sm"
            : "bg-slate-800 text-slate-100 rounded-bl-sm"
        }`}
      >
        {message.content}
        {message.streaming && <span className="inline-block w-1.5 h-4 ml-0.5 align-middle bg-slate-400 animate-pulse" />}
      </div>
    </div>
  );
}
