import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "./navItems.js";
import { useRole } from "../../context/RoleContext.jsx";
import Icon from "../../design-system/icons.jsx";

export default function MobileBottomNavigation() {
  const { role } = useRole();
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || role === "Administrator" || item.roles.includes(role)
  ).slice(0, 5);

  return (
    <nav className="bottomnav" aria-label="Primary">
      {visibleItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `bottomnav-link ${isActive ? "is-active" : ""}`}
        >
          <span className="bottomnav-icon"><Icon name={item.icon} /></span>
          <span className="bottomnav-label">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
