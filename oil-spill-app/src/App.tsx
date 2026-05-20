import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import HomePage from "@/pages/Home";
import MapPage from "@/pages/MapPage";
import AnalyzePage from "@/pages/Analyze";
import ChatbotPage from "@/pages/Chatbot";
import ReportsPage from "@/pages/Reports";
import About from "@/pages/About";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/chatbot" element={<ChatbotPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/about" element={<About />} />
        <Route path="/solutions" element={<Navigate to="/reports" replace />} />
        <Route path="/solutions-report" element={<Navigate to="/reports" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
