import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "./navItems.js";
import { useRole } from "../../context/RoleContext.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import api from "../../api/client.js";
import Icon, { IconMark, IconSettings } from "../../design-system/icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

export default function TopNavigation() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const menuRef = useRef(null);
  const { role, isReadOnly } = useRole();
  const { user, logout } = useAuth();

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
        <NavLink to="/" className="topnav-brand" end>
          <span className="topnav-brand-icon"><IconMark /></span>
          <span className="topnav-brand-name">TRIAL<b>MIND</b></span>
        </NavLink>

        <div className="topnav-links">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `topnav-link ${isActive ? "is-active" : ""}`}
            >
              <span className="topnav-link-icon"><Icon name={item.icon} /></span>
              <span className="topnav-link-label">{item.label}</span>
            </NavLink>
          ))}
        </div>

        <div className="topnav-actions">
          <ThemeToggle />
          <div className="topnav-user" title={`Signed in as ${user?.username}`}>
            <span className="topnav-user-role">{user?.display_name || role}</span>
          </div>
          <button className="topnav-logout" onClick={logout}>Log out</button>
          {isReadOnly && (
            <span className="badge normal" style={{ fontSize: 10 }} title="This role can view but not modify data.">
              READ-ONLY
            </span>
          )}
          {role === "Administrator" && (
            <div className="topnav-menu" ref={menuRef}>
              <button
                className="topnav-gear"
                onClick={() => setMenuOpen((v) => !v)}
                aria-label="Administration"
                aria-expanded={menuOpen}
              >
                <IconSettings />
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
