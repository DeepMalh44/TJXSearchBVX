import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import { createMsal } from "./auth";
import App from "./App";
import "./styles.css";

const msal = await createMsal();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MsalProvider instance={msal}>
      <App />
    </MsalProvider>
  </StrictMode>,
);