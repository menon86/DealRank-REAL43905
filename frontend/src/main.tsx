import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { EntryGate } from "./components/EntryGate";
import "./styles.css";
import "./theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <EntryGate>
      <App />
    </EntryGate>
  </React.StrictMode>,
);
