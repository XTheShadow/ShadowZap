import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "react-toastify";
import Cookies from 'js-cookie'; // Added for session management

const API_URL = "http://127.0.0.1:8000";

// Helper function to safely make API calls
const safeApiCall = async (url, method = 'get', data = null) => {
  try {
    const config = { 
      validateStatus: status => status < 500,
      timeout: 5000 // Add a 5-second timeout
    };
    if (method.toLowerCase() === 'get') {
      return await axios.get(url, config);
    } else if (method.toLowerCase() === 'post') {
      return await axios.post(url, data, config);
    }
  } catch (error) {
    console.log(`API call to ${url} failed:`, error);
    return { status: 404, data: null };
  }
};

const DashboardPage = () => {
  const [stats, setStats] = useState({
    totalScans: 0,
    completedScans: 0,
    failedScans: 0,
    enhancedReports: 0,
    vulnerabilitiesByType: {},
    recentTargets: [],
    recentSessions: []
  });
  
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const initialLoadRef = useRef(true);
  const isManualRefreshRef = useRef(false);
  const loadingTimeoutRef = useRef(null);
  const sessionId = Cookies.get('session_id'); // Get current user's session ID

  // Load data from local storage as fallback
  const loadLocalData = useCallback(() => {
    const savedScans = JSON.parse(localStorage.getItem("scanHistory") || "[]");
    
    // Filter scans by current session if available
    const userScans = sessionId 
      ? savedScans.filter(scan => scan.session_id === sessionId)
      : savedScans;
    
    // Calculate statistics
    const totalScans = userScans.length;
    const completedScans = userScans.filter(scan => scan.status === "Completed").length;
    const failedScans = userScans.filter(scan => scan.status === "Failed").length;
    const enhancedReports = userScans.filter(scan => scan.report_type === "ENHANCED").length;
    
    // Get unique targets
    const uniqueTargets = [...new Set(userScans.map(scan => scan.target_url))];
    const recentTargets = uniqueTargets.slice(0, 5);
    
    // Update state
    setStats({
      totalScans,
      completedScans,
      failedScans,
      enhancedReports,
      vulnerabilitiesByType: {},
      recentTargets,
      recentSessions: []
    });
    
    // Only show toast for manual refresh
    if (isManualRefreshRef.current) {
      toast.info("Using local data - couldn't connect to server");
      isManualRefreshRef.current = false;
    }
    
    // Always set loading to false when done
    setLoading(false);
    
    // Clear any loading timeout
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }
  }, [sessionId]);

  // Use useCallback to memoize the fetchDashboardData function
  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    
    // Set a timeout to ensure loading state doesn't get stuck
    loadingTimeoutRef.current = setTimeout(() => {
      if (loading) {
        console.log("Dashboard data fetch timeout - using local data");
        loadLocalData();
      }
    }, 10000); // 10 seconds timeout
    
    try {
      // First try to get data from API with session filter
      let endpoint = `${API_URL}/dashboard`;
      
      // Add session filter if available
      if (sessionId) {
        endpoint = `${API_URL}/dashboard?session_id=${sessionId}`;
      }
      
      const response = await safeApiCall(endpoint);
      
      // If endpoint doesn't exist, use local data
      if (response.status === 404 || !response.data) {
        loadLocalData();
        return;
      }
      
      if (response.data) {
        // Validate the data to ensure consistency
        const data = response.data;
        
        // Ensure all counts are numbers
        const totalScans = parseInt(data.totalScans) || 0;
        const completedScans = parseInt(data.completedScans) || 0;
        const failedScans = parseInt(data.failedScans) || 0;
        const enhancedReports = parseInt(data.enhancedReports) || 0;
        
        // Ensure completed + failed scans <= total scans
        const validCompletedScans = Math.min(completedScans, totalScans);
        const validFailedScans = Math.min(failedScans, totalScans - validCompletedScans);
        
        // Ensure vulnerability counts are numbers
        const vulnTypes = data.vulnerabilitiesByType || {};
        const validVulnTypes = {
          high: parseInt(vulnTypes.high) || 0,
          medium: parseInt(vulnTypes.medium) || 0,
          low: parseInt(vulnTypes.low) || 0,
          info: parseInt(vulnTypes.info) || 0
        };
        
        // Set the data with validated values
        setStats({
          totalScans: totalScans,
          completedScans: validCompletedScans,
          failedScans: validFailedScans,
          enhancedReports: enhancedReports,
          vulnerabilitiesByType: validVulnTypes,
          recentTargets: Array.isArray(data.recentTargets) ? data.recentTargets.filter(t => t) : [],
          recentSessions: Array.isArray(data.recentSessions) ? data.recentSessions.filter(s => s && s.target_url) : []
        });
        
        // Only show success toast for manual refresh
        if (isManualRefreshRef.current) {
          toast.success("Dashboard data updated");
          isManualRefreshRef.current = false;
        }
      } else {
        // Fallback to local storage if API returns empty data
        loadLocalData();
        return;
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
      // Continue with local data if API fails
      loadLocalData();
      return;
    }
    
    // Always set loading to false when done
    setLoading(false);
    initialLoadRef.current = false;
    
    // Clear any loading timeout
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }
  }, [loadLocalData, sessionId, loading]);

  // Effect for initial load only
  useEffect(() => {
    // Initial load
    if (initialLoadRef.current) {
      fetchDashboardData();
      initialLoadRef.current = false;
    }
    // Manual refresh
    else if (refreshKey > 0) {
      fetchDashboardData();
    }
    
    // Clean up timeout on unmount
    return () => {
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
        loadingTimeoutRef.current = null;
      }
    };
  }, [refreshKey, fetchDashboardData]);

  const handleRefresh = () => {
    // Don't allow refresh if already loading
    if (loading) return;
    
    // Manual refresh - increment the key to trigger the effect
    setRefreshKey(oldKey => oldKey + 1);
    isManualRefreshRef.current = true;
    toast.info("Refreshing dashboard data...");
  };

  return (
    <div className="zap-dashboard">
      <div className="zap-dashboard-header">
        <h1>Dashboard</h1>
        <button 
          onClick={handleRefresh} 
          className="zap-refresh-button"
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      
      {loading && Object.values(stats).every(val => !val) ? (
        <div className="zap-loading">Loading dashboard data...</div>
      ) : (
        <div className="zap-dashboard-grid">
          <div className="zap-dashboard-card">
            <h3>Scan Statistics</h3>
            <div className="zap-stat-grid">
              <div className="zap-stat">
                <div className="zap-stat-value">{stats.totalScans}</div>
                <div className="zap-stat-label">Total Scans</div>
              </div>
              <div className="zap-stat">
                <div className="zap-stat-value">{stats.completedScans}</div>
                <div className="zap-stat-label">Completed</div>
              </div>
              <div className="zap-stat">
                <div className="zap-stat-value">{stats.failedScans}</div>
                <div className="zap-stat-label">Failed</div>
              </div>
              <div className="zap-stat">
                <div className="zap-stat-value">{stats.enhancedReports}</div>
                <div className="zap-stat-label">Enhanced Reports</div>
              </div>
            </div>
          </div>
          
          <div className="zap-dashboard-card">
            <h3>Recent Targets</h3>
            {stats.recentTargets && stats.recentTargets.length > 0 ? (
              <ul className="zap-target-list">
                {stats.recentTargets.map((target, index) => (
                  <li key={index} className="zap-target-item">{target}</li>
                ))}
              </ul>
            ) : (
              <p>No targets scanned yet</p>
            )}
          </div>
          
          {stats.vulnerabilitiesByType && Object.keys(stats.vulnerabilitiesByType).length > 0 && (
            <div className="zap-dashboard-card zap-full-width">
              <h3>Vulnerabilities by Type</h3>
              <div className="zap-vuln-chart">
                {Object.entries(stats.vulnerabilitiesByType).map(([type, count], index) => (
                  <div key={index} className="zap-vuln-bar">
                    <div className="zap-vuln-label">{type}</div>
                    <div className="zap-vuln-bar-container">
                      <div 
                        className="zap-vuln-bar-fill"
                        style={{ 
                          width: `${Math.min(count * 5, 100)}%`,
                          backgroundColor: getVulnColor(type)
                        }}
                      ></div>
                      <div className="zap-vuln-count">{count}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {stats.recentSessions && stats.recentSessions.length > 0 && (
            <div className="zap-dashboard-card">
              <h3>Recent Scans</h3>
              <ul className="zap-session-list">
                {stats.recentSessions.map((session, index) => (
                  <li key={index} className="zap-session-item">
                    <div className="zap-session-target">{session.target_url}</div>
                    <div className="zap-session-date">
                      {new Date(session.timestamp).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Helper function to get color based on vulnerability type
const getVulnColor = (type) => {
  const colors = {
    'High': '#ff3333',
    'Medium': '#ff9933',
    'Low': '#ffcc33',
    'Informational': '#33ccff',
    'high': '#ff3333',
    'medium': '#ff9933',
    'low': '#ffcc33',
    'info': '#33ccff'
  };
  
  return colors[type] || '#888888';
};

export default DashboardPage; 