import { Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext.jsx";
import { RoleProvider } from "./context/RoleContext.jsx";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import DemoBanner from "./components/layout/DemoBanner.jsx";
import TopNavigation from "./components/layout/TopNavigation.jsx";
import MobileBottomNavigation from "./components/layout/MobileBottomNavigation.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Studies from "./pages/Studies.jsx";
import StudyDetail from "./pages/StudyDetail.jsx";
import RegulatoryDrafting from "./pages/RegulatoryDrafting.jsx";
import LabScheduling from "./pages/LabScheduling.jsx";
import PatientDirectory from "./pages/PatientDirectory.jsx";
import Safety from "./pages/Safety.jsx";
import Regulatory from "./pages/Regulatory.jsx";
import AuditTrail from "./pages/AuditTrail.jsx";
import Interoperability from "./pages/Interoperability.jsx";

// Role-based login authentication: nothing in the app shell renders until
// a demo account has signed in via /auth/login (see AuthContext.jsx). The
// role that gates navigation/RBAC throughout the rest of the app (see
// RoleContext.jsx, navItems.js) is the one the account logged in with, not
// a free-standing client-side picker anymore.
function AuthGate() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return (
      <ThemeProvider>
        <Login />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider>
      <RoleProvider>
        <div className="app-shell">
          <DemoBanner />
          <TopNavigation />
          <main className="main-content fade-in">
            <Routes>
              {/* TrialMind's screening console now lives inside the single
                  Dashboard page (see pages/Dashboard.jsx) instead of a
                  separate route -- /trialmind redirects here for any old
                  links/bookmarks. */}
              <Route path="/" element={<Dashboard />} />
              <Route path="/trialmind" element={<Navigate to="/" replace />} />
              <Route path="/studies" element={<Studies />} />
              <Route path="/studies/:id" element={<StudyDetail />} />
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

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
