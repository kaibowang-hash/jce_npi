import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/app";
import { I18nProvider } from "./i18n/runtime";
import { DisplayBrandBootstrap } from "./ui-adapters/display-brand";
import "./generated/tokens.css";
import "./styles/app.css";

const root = document.getElementById("root");
if (!root) throw new Error("Application root was not found.");

createRoot(root).render(
  <StrictMode>
    <I18nProvider>
      <DisplayBrandBootstrap>
        <App />
      </DisplayBrandBootstrap>
    </I18nProvider>
  </StrictMode>,
);
