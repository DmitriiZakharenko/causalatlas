import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import StandaloneDemo from "./standalone-demo";
import "./index.css";
import "./App.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StandaloneDemo />
  </StrictMode>,
);
