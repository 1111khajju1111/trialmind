import { Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext.jsx";
import { RoleProvider } from "./context/RoleContext.jsx";
import DemoBanner from "./components/layout/DemoBanner.jsx";
import TopNavigation from "./components/layout/TopNavigation.jsx";
import MobileBottomNavigation from "./components/layout/MobileBottomNavigation.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Studies from "./pages/Studies.jsx";
import StudyDetail from "./pages/StudyDetail.jsx";
import TrialMind from "./pages/TrialMind.jsx";
import RegulatoryDrafting from "./pages/RegulatoryDrafting.jsx";
import LabScheduling from "./pages/LabScheduling.jsx";
import PatientDirectory from "./pages/PatientDirectory.jsx";
import Safety from "./pages/Safety.jsx";
import Regulatory from "./pages/Regulatory.jsx";
import AuditTrail from "./pages/AuditTrail.jsx";
import Interoperability from "./pages/Interoperability.jsx";

export default function App() {
  return (
    <ThemeProvider>
      <RoleProvider>
        <div className="app-shell">
          <DemoBanner />
          <TopNavigation />
          <main className="main-content fade-in">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/studies" element={<Studies />} />
              <Route path="/studies/:id" element={<StudyDetail />} />
              <Route path="/trialmind" element={<TrialMind />} />
              <Route path="/regulatory" element={<RegulatoryDrafting />} />
              <Route path="/lab-scheduling" element={<LabScheduling />} />
              <Route path="/patients" element={<PatientDirectory />} />
              <Route path="/safety" element={<Safety />} />
              <Route path="/compliance" element={<Regulatory />} />
              <Route path="/audit" element={<AuditTrail />} />
              <Route path="/interop" element={<Interoperability />} />
            </Routes>
          </main>
          <MobileBottomNavigation />
        </div>
      </RoleProvider>
    </ThemeProvider>
  );
}
