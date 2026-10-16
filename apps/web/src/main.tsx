import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./tw.css";
import { ThemeProvider } from "./theme";
import { KeyProvider } from "./ui";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <KeyProvider>
        <App />
      </KeyProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
