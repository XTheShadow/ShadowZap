import React from "react";
import { NavLink } from "react-router-dom";
import hackerIcon from "../hacker-icon.png";

const Navigation = () => {
  return (
    <nav className="zap-nav">
      <div className="zap-nav-brand">
        <img src={hackerIcon} alt="ShadowZap Icon" className="zap-nav-icon" />
        <h1 className="zap-nav-title">ShadowZap</h1>
      </div>
      
      <div className="zap-nav-links">
        <NavLink 
          to="/" 
          className={({ isActive }) => 
            isActive ? "zap-nav-link zap-nav-active" : "zap-nav-link"
          }
          end
        >
          New Scan
        </NavLink>
        
        <NavLink 
          to="/history" 
          className={({ isActive }) => 
            isActive ? "zap-nav-link zap-nav-active" : "zap-nav-link"
          }
        >
          History
        </NavLink>
        
        <NavLink 
          to="/dashboard" 
          className={({ isActive }) => 
            isActive ? "zap-nav-link zap-nav-active" : "zap-nav-link"
          }
        >
          Dashboard
        </NavLink>
      </div>
    </nav>
  );
};

export default Navigation; 