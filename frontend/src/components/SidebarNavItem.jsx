import React from "react";
import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import { useReducedMotionPreference } from "../hooks/useReducedMotionPreference";
import { Tooltip, TooltipTrigger, TooltipContent } from "./ui/tooltip";

export const SidebarNavItem = ({ path, label, icon: Icon, preference = false, collapsed = false }) => {
  const reduced = useReducedMotionPreference();
  const link = <NavLink end={path === "/"} to={path} data-testid={`nav-${path === "/" ? "dashboard" : path.slice(1)}`}
    aria-label={label} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
    {({ isActive }) => <>
      {isActive && <motion.span className="nav-motion-indicator" layoutId="main-active-menu"
        data-testid={preference ? "preferences-navigation-indicator" : "main-navigation-indicator"} aria-hidden="true"
        transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 440, damping: 36 }} />}
      <Icon size={18} aria-hidden="true" /><span className="nav-item-label">{label}</span>
      {path === "/" && <span className="nav-active-dot" aria-hidden="true" />}
    </>}
  </NavLink>;
  if (!collapsed) return link;
  return <Tooltip delayDuration={80}>
    <TooltipTrigger asChild><div className="nav-tooltip-wrap">{link}</div></TooltipTrigger>
    <TooltipContent side="right" sideOffset={10} className="sidebar-tooltip" data-testid={`nav-tooltip-${path === "/" ? "dashboard" : path.slice(1)}`}>{label}</TooltipContent>
  </Tooltip>;
};
