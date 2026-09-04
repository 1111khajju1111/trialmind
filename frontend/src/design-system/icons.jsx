/**
 * TrialMind icon system.
 * One consistent 1.75px stroke, 24x24 grid, geometric line-icon family —
 * replaces the emoji used throughout the previous UI. Keeping every icon
 * in this single file makes the "one icon family" rule easy to enforce:
 * new icons should match this stroke weight / corner radius / viewBox.
 */
const base = {
  width: "1em",
  height: "1em",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function Svg({ children, className, style }) {
  return (
    <svg {...base} className={`tm-icon ${className || ""}`} style={style} aria-hidden="true">
      {children}
    </svg>
  );
}

export const IconMark = (p) => ( // brand mark — nested hex core, stands in for the AgentCore
  <Svg {...p}>
    <path d="M12 2.5 20.5 7.25V16.75L12 21.5 3.5 16.75V7.25Z" />
    <path d="M12 8 16 10.25V14.75L12 17 8 14.75V10.25Z" />
    <path d="M12 2.5V8M12 17V21.5M3.5 7.25 8 10.25M16 10.25 20.5 7.25M8 14.75 3.5 16.75M16 14.75 20.5 16.75" opacity="0.5" />
  </Svg>
);

export const IconDashboard = (p) => (
  <Svg {...p}><path d="M4 13h6V4H4v9ZM14 20h6V4h-6v16ZM4 20h6v-4H4v4Z" /></Svg>
);
export const IconStudies = (p) => (
  <Svg {...p}><path d="M4 20V6a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /><path d="M14 4v5h5M8 12h8M8 16h5" /></Svg>
);
export const IconTrialMind = IconMark;
export const IconPatients = (p) => (
  <Svg {...p}><circle cx="9" cy="8" r="3" /><path d="M3.5 20a5.5 5.5 0 0 1 11 0" /><circle cx="17.5" cy="8.5" r="2.5" /><path d="M15.2 13.2A5 5 0 0 1 20.5 20" /></Svg>
);
export const IconSafety = (p) => (
  <Svg {...p}><path d="M12 3 5 6v5.5c0 4.4 2.9 7.7 7 8.5 4.1-.8 7-4.1 7-8.5V6Z" /><path d="M9.5 12 11.5 14 15 10" /></Svg>
);
export const IconCompliance = (p) => (
  <Svg {...p}><path d="M12 3v18M7 6l-4 8a4 4 0 0 0 8 0Zm10 0-4 8a4 4 0 0 0 8 0ZM5 21h14M7 6h10" /></Svg>
);
export const IconRegulatory = (p) => (
  <Svg {...p}><path d="M6 3h9l3 3v15H6Z" /><path d="M15 3v3h3M9 12h6M9 15h6M9 9h3" /></Svg>
);
export const IconLab = (p) => (
  <Svg {...p}><path d="M9 2h6M10 2v6.2L4.8 18a2 2 0 0 0 1.8 3h10.8a2 2 0 0 0 1.8-3L14 8.2V2" /><path d="M7.5 15h9" /></Svg>
);
export const IconInterop = (p) => (
  <Svg {...p}><rect x="3" y="9" width="6" height="6" rx="1" /><rect x="15" y="9" width="6" height="6" rx="1" /><path d="M9 12h6" /></Svg>
);
export const IconAudit = (p) => (
  <Svg {...p}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3M11 8v3l2 1" /></Svg>
);
export const IconCheck = (p) => (<Svg {...p}><path d="M4 12.5 9.5 18 20 6" /></Svg>);
export const IconCross = (p) => (<Svg {...p}><path d="M5 5l14 14M19 5 5 19" /></Svg>);
export const IconWarning = (p) => (
  <Svg {...p}><path d="M12 3 22 20H2Z" /><path d="M12 10v4" /><circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none" /></Svg>
);
export const IconClock = (p) => (<Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></Svg>);
export const IconSearch = (p) => (<Svg {...p}><circle cx="10.5" cy="10.5" r="6.5" /><path d="M20 20l-5-5" /></Svg>);
export const IconSettings = (p) => (
  <Svg {...p}><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3H9.8l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5A7 7 0 0 0 5 12a7 7 0 0 0 .1 1.2l-2 1.6 2 3.4 2.3-1a7 7 0 0 0 2 1.2l.4 2.6h4.4l.4-2.6a7 7 0 0 0 2-1.2l2.3 1 2-3.4-2-1.6c.07-.4.1-.8.1-1.2Z" /></Svg>
);
export const IconChevronRight = (p) => (<Svg {...p}><path d="m9 6 6 6-6 6" /></Svg>);
export const IconArrowRight = (p) => (<Svg {...p}><path d="M4 12h15M13 6l6 6-6 6" /></Svg>);
export const IconPulse = (p) => (<Svg {...p}><path d="M3 12h4l2-7 4 14 2-7h6" /></Svg>);
export const IconFolder = (p) => (<Svg {...p}><path d="M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z" /></Svg>);
export const IconSun = (p) => (<Svg {...p}><circle cx="12" cy="12" r="4.2" /><path d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" /></Svg>);
export const IconMoon = (p) => (<Svg {...p}><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" /></Svg>);
export const IconTrend = (p) => (<Svg {...p}><path d="M3 17l6-6 4 4 8-9M15 6h6v6" /></Svg>);
export const IconBell = (p) => (<Svg {...p}><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" /><path d="M10 19a2 2 0 0 0 4 0" /></Svg>);
export const IconLink = (p) => (<Svg {...p}><path d="M9 15 15 9M8 16l-2 2a3.5 3.5 0 0 1-5-5l3-3a3.5 3.5 0 0 1 5 0M16 8l2-2a3.5 3.5 0 0 1 5 5l-3 3a3.5 3.5 0 0 1-5 0" /></Svg>);
export const IconFlag = (p) => (<Svg {...p}><path d="M5 3v18M5 4h13l-3 4 3 4H5" /></Svg>);
export const IconLayers = (p) => (<Svg {...p}><path d="m12 3 9 5-9 5-9-5Z" /><path d="m3 13 9 5 9-5M3 8v5M21 8v5" /></Svg>);
export const IconBuilding = (p) => ( // sites / facilities
  <Svg {...p}><rect x="4" y="3" width="12" height="18" rx="1" /><path d="M9 7h2M9 11h2M9 15h2M16 10h4v11h-4" /></Svg>
);
export const IconCalendar = (p) => ( // milestones / dates
  <Svg {...p}><rect x="3.5" y="5" width="17" height="15" rx="1.5" /><path d="M3.5 9.5h17M8 3v4M16 3v4M8 14h1M12 14h1M16 14h1" /></Svg>
);
export const IconClipboard = (p) => ( // cases / logs
  <Svg {...p}><rect x="5.5" y="4.5" width="13" height="17" rx="1.5" /><path d="M9 4.5V3.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M8.5 11h7M8.5 15h7" /></Svg>
);
export const IconAlertCircle = (p) => ( // critical alerts / SAE
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5.5" /><circle cx="12" cy="16.3" r="0.6" fill="currentColor" stroke="none" /></Svg>
);
export const IconFlask = (p) => ( // equipment
  <Svg {...p}><path d="M9 2h6M10 2v6.4L4.9 17a2 2 0 0 0 1.8 3h10.6a2 2 0 0 0 1.8-3L14 8.4V2" /><path d="M8 13.5h8" /></Svg>
);
export const IconMicroscope = (p) => ( // samples / lab
  <Svg {...p}><path d="M9 20h7M11 20v-3.2a4.5 4.5 0 1 1 3-8.5" /><path d="M12.5 8.3 17 3.8l1.5 1.5-4.5 4.5" /><path d="M5.5 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" /></Svg>
);
export const IconExport = (p) => ( // data export
  <Svg {...p}><path d="M12 3v11M8 7l4-4 4 4" /><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></Svg>
);
export const IconMinus = (p) => (<Svg {...p}><path d="M5 12h14" /></Svg>);
export const IconCompass = (p) => ( // agent runs / navigation
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="m14.5 9.5-1.7 5.3-5.3 1.7 1.7-5.3Z" /></Svg>
);
export const IconRadar = (p) => ( // safety signal detection — concentric sweep + flagged point
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="12" r="5" opacity="0.5" />
    <circle cx="12" cy="12" r="1.5" opacity="0.5" />
    <path d="M12 12 17 7" />
    <circle cx="16.5" cy="8.5" r="1.4" fill="currentColor" stroke="none" />
  </Svg>
);
export const IconDot = ({ color, ...p }) => (
  <Svg {...p}><circle cx="12" cy="12" r="6" fill={color || "currentColor"} stroke="none" /></Svg>
);

export const ICONS = {
  dashboard: IconDashboard,
  studies: IconStudies,
  trialmind: IconTrialMind,
  patients: IconPatients,
  safety: IconSafety,
  compliance: IconCompliance,
  regulatory: IconRegulatory,
  lab: IconLab,
  interop: IconInterop,
  audit: IconAudit,
  building: IconBuilding,
  calendar: IconCalendar,
  clipboard: IconClipboard,
  alertCircle: IconAlertCircle,
  flask: IconFlask,
  microscope: IconMicroscope,
  export: IconExport,
  minus: IconMinus,
  dot: IconDot,
  compass: IconCompass,
  radar: IconRadar,
};

export default function Icon({ name, ...rest }) {
  const Cmp = ICONS[name];
  if (!Cmp) return null;
  return <Cmp {...rest} />;
}
