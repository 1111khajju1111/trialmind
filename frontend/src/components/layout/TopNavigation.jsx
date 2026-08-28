import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import ThemeToggle from "./ThemeToggle.jsx";
import { NAV_ITEMS } from "./navItems.js";
import { useRole, ROLES } from "../../context/RoleContext.jsx";
import api from "../../api/client.js";

export default function TopNavigation() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const menuRef = useRef(null);
  const { role, setRole, isReadOnly } = useRole();

  useEffect(() => {
    function onClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const resetDemoData = async () => {
    if (!window.confirm("Reset all demo data? This clears all matches and approvals.")) return;
    setResetting(true);
    try {
      await api.resetDemo();
      window.location.reload();
    } finally {
      setResetting(false);
      setMenuOpen(false);
    }
  };

  // Priority 5 -- RBAC (thin, demo-appropriate). Administrator always sees
  // every nav item; everyone else only sees items whose `roles` list
  // includes their current role (or items open to everyone, roles: null).
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || role === "Administrator" || item.roles.includes(role)
  );

  return (
    <header className="topnav-wrap">
      <nav className="topnav">
        <div className="topnav-brand">
          <span className="topnav-brand-icon">🧬</span>
          <span className="topnav-brand-name">PharmaAI</span>
        </div>

        <div className="topnav-links">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `topnav-link ${isActive ? "is-active" : ""}`}
            >
              <span className="topnav-link-icon">{item.icon}</span>
              <span className="topnav-link-label">{item.label}</span>
            </NavLink>
          ))}
        </div>

        <div className="topnav-actions">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            title="Acting role (Priority 5 — Role-Based Access). No login in this demo build; every API request carries this role and the backend enforces it."
            style={{ fontSize: 12.5, padding: "4px 8px" }}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          {isReadOnly && (
            <span className="badge normal" style={{ fontSize: 10.5 }} title="This role can view but not modify data.">
              READ-ONLY
            </span>
          )}
          <ThemeToggle />
          {role === "Administrator" && (
            <div className="topnav-menu" ref={menuRef}>
              <button
                className="topnav-gear"
                onClick={() => setMenuOpen((v) => !v)}
                aria-label="Administration"
                aria-expanded={menuOpen}
              >
                ⚙️
              </button>
              {menuOpen && (
                <div className="topnav-dropdown">
                  <div className="topnav-dropdown-heading">Administration</div>
                  <button
                    className="topnav-dropdown-item topnav-dropdown-danger"
                    onClick={resetDemoData}
                    disabled={resetting}
                  >
                    {resetting ? "Resetting…" : "Reset Demo Data"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </nav>
    </header>
  );
}
