import { BrowserRouter, Routes, Route } from "react-router-dom";
import NavBar from "./components/NavBar";
import LaunchPage from "./pages/LaunchPage";
import RunDetailPage from "./pages/RunDetailPage";
import GraphExplorerPage from "./pages/GraphExplorerPage";
import DiseasePathogenesisPage from "./pages/DiseasePathogenesisPage";
import EvalDashboardPage from "./pages/EvalDashboardPage";
import ArchitecturePage from "./pages/ArchitecturePage";
import EvidenceDashboardPage from "./pages/EvidenceDashboardPage";
import PresentationPage from "./pages/PresentationPage";
import DemoReplayPage from "./pages/DemoReplayPage";
import "./App.css";

export function AppContent() {
  return (
    <>
      <NavBar />
      <main>
        <Routes>
          <Route path="/" element={<LaunchPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/graphs" element={<GraphExplorerPage />} />
          <Route path="/graphs/:diseaseSlug/pathogenesis" element={<DiseasePathogenesisPage />} />
          <Route path="/eval" element={<EvalDashboardPage />} />
          <Route path="/architecture" element={<ArchitecturePage />} />
          <Route path="/evidence" element={<EvidenceDashboardPage />} />
          <Route path="/presentation" element={<PresentationPage />} />
          <Route path="/demo" element={<DemoReplayPage />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
