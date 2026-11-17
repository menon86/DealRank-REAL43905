import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { EntryGate } from "./components/EntryGate";
import { SignInGate } from "./components/SignInGate";
import { authEnabled } from "./lib/auth";
import "./styles.css";
import "./theme.css";

// With Google/Microsoft client ids configured, require a real sign-in; without
// them (local dev against AUTH_REQUIRED=false) keep the demo access-code screen.
const Gate = authEnabled ? SignInGate : EntryGate;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Gate>
      <App />
    </Gate>
  </React.StrictMode>,
);
