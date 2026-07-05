import { BrowserRouter, Routes, Route } from "react-router-dom";
import NavBar from "./components/NavBar";
import LaunchPage from "./pages/LaunchPage";
import RunDetailPage from "./pages/RunDetailPage";
import GraphExplorerPage from "./pages/GraphExplorerPage";
import EvalDashboardPage from "./pages/EvalDashboardPage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <NavBar />
      <main>
        <Routes>
          <Route path="/" element={<LaunchPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/graphs" element={<GraphExplorerPage />} />
          <Route path="/eval" element={<EvalDashboardPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
