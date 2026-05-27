import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ChatView from "./components/ChatView";
import Dashboard from "./components/Dashboard";
import EvaluationView from "./components/EvaluationView";
import { StoreProvider } from "./store";

export default function App() {
  return (
    <StoreProvider>
      <div className="flex h-screen w-screen overflow-hidden">
        <Sidebar />
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
    </StoreProvider>
  );
}
