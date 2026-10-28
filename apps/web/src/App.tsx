/** GlobalIntelligence shell: RTL sidebar (18 sections) + topbar + hash routes. */
import AI from "./pages/ai";
import Chat from "./pages/chat";
import { DecisionsPage, ForecastPage, ScenariosPage } from "./pages/analysis";
import Connections from "./pages/connections";
import Dashboard from "./pages/dashboard";
import Debate from "./pages/debate";
import Keys from "./pages/keys";
import { GeoPage, IranPage } from "./pages/geo";
import Markets from "./pages/markets";
import { HelpPage, HistoryPage, OpsPage, SearchPage } from "./pages/misc";
import { SettingsPanel } from "./pages/settings";
import ScreeningOps from "./pages/screening";
import News from "./pages/news";
import { EvaluationPage, PortfolioPage } from "./pages/portfolio";
import Society from "./pages/society";
import Sources from "./pages/sources";
import { MacroPage, WorldPage } from "./pages/world";
import { useRoute } from "./router";
import { Shell } from "./ui";

export default function App() {
  const route = useRoute();
  return (
    <Shell>
      {route.name === "dashboard" && <Dashboard />}
      {route.name === "news" && <News param={route.param} />}
      {route.name === "sources" && <Sources />}
      {route.name === "ai" && <AI />}
      {route.name === "chat" && <Chat />}
      {route.name === "world" && <WorldPage />}
      {route.name === "macro" && <MacroPage />}
      {route.name === "geo" && <GeoPage />}
      {route.name === "iran" && <IranPage />}
      {route.name === "markets" && <Markets />}
      {route.name === "forecast" && <ForecastPage />}
      {route.name === "debate" && <Debate param={route.param} />}
      {route.name === "scenarios" && <ScenariosPage />}
      {route.name === "decisions" && <DecisionsPage />}
      {route.name === "portfolio" && <PortfolioPage />}
      {route.name === "evaluation" && <EvaluationPage />}
      {route.name === "history" && <HistoryPage />}
      {route.name === "ops" && <OpsPage />}
      {route.name === "screening" && <ScreeningOps />}
      {route.name === "settings" && <SettingsPanel />}
      {route.name === "help" && <HelpPage />}
      {route.name === "search" && <SearchPage key={route.param} param={route.param} />}
      {route.name === "connections" && <Connections />}
      {route.name === "society" && <Society />}
      {route.name === "keys" && <Keys />}
    </Shell>
  );
}
