import React, { useState, useEffect, useRef } from "react";
import ScanForm from "../components/ScanForm";
import RealtimeStatus from "../components/RealtimeStatus";
import { toast } from "react-toastify";
import Cookies from 'js-cookie';
import axios from "axios";

const API_URL = "http://127.0.0.1:8000";

const HomePage = () => {
  const [currentScan, setCurrentScan] = useState(null);
  const [scanKey, setScanKey] = useState(0); // Add a key to force RealtimeStatus component remounting
  const hasShownResumeToastRef = useRef(false);
  const hasShownReportReadyToastRef = useRef(false);

  // Check for existing session on component mount
  useEffect(() => {
    const sessionId = Cookies.get('session_id');
    
    // If there's a session ID, check if there's an active scan
    if (sessionId) {
      const checkForActiveScan = async () => {
        try {
          // First check if the endpoint exists
          const checkEndpoint = await axios.get(`${API_URL}/scan-status`, { validateStatus: false })
            .catch(() => ({ status: 404 }));
            
          // Only proceed if endpoint exists or fallback to a known endpoint
          const endpoint = checkEndpoint.status !== 404 
            ? `${API_URL}/active-scan?session_id=${sessionId}`
            : `${API_URL}/scan-by-session/${sessionId}`;
            
          const response = await axios.get(endpoint)
            .catch(error => {
              console.log("No active scan found or endpoint not available");
              return { data: null };
            });
            
          if (response.data && response.data.task_id) {
            // Set the current scan data
            setCurrentScan({
              ...response.data,
              session_id: sessionId
            });
            
            // Increment the key to force remounting of RealtimeStatus
            setScanKey(prevKey => prevKey + 1);
            
            // Show resume toast only once per session
            if (!hasShownResumeToastRef.current) {
              hasShownResumeToastRef.current = true;
              toast.info("Resuming your previous scan session");
            }
          }
        } catch (error) {
          console.error("Error checking for active scan:", error);
        }
      };
      
      checkForActiveScan();
    }
  }, []);

  const handleScanComplete = (scanData) => {
    // Clear previous scan data first
    setCurrentScan(null);
    
    // Use setTimeout to ensure the component unmounts before setting new data
    setTimeout(() => {
      // Save scan data to localStorage for persistence
      const scanHistory = JSON.parse(localStorage.getItem("scanHistory") || "[]");
      
      // Get current session ID
      const sessionId = Cookies.get('session_id');
      
      scanHistory.unshift({
        ...scanData,
        timestamp: new Date().toISOString(),
        session_id: sessionId || scanData.web_session_id
      });
      
      localStorage.setItem("scanHistory", JSON.stringify(scanHistory.slice(0, 50))); // Keep last 50 scans
      
      setCurrentScan({
        ...scanData,
        session_id: sessionId || scanData.web_session_id
      });
      
      // Increment the key to force remounting of RealtimeStatus
      setScanKey(prevKey => prevKey + 1);
      
      // Reset toast flags when starting a new scan
      hasShownReportReadyToastRef.current = false;
      
      // Show toast for new scan
      toast.info(`Starting scan of ${scanData.target_url}`);
      
      // Trigger dashboard update - but only if we know the endpoint exists
      try {
        // Use a simple GET request to check if the endpoint exists
        axios.head(`${API_URL}/dashboard`)
          .then(() => {
            // If the dashboard endpoint exists, assume update-dashboard might exist too
            axios.post(`${API_URL}/update-dashboard`, { 
              session_id: sessionId || scanData.web_session_id,
              task_id: scanData.task_id,
              target_url: scanData.target_url
            }).catch(err => {
              // Silently handle errors for this optional endpoint
              console.log("Dashboard update not available", err);
            });
          })
          .catch(() => {
            console.log("Dashboard endpoints not available");
          });
      } catch (error) {
        console.log("Error checking dashboard endpoints:", error);
      }
    }, 100);
  };
  
  const handleStatusUpdate = (statusData) => {
    // Only show notifications for important status changes
    if (statusData.status === "Completed" && !hasShownReportReadyToastRef.current) {
      hasShownReportReadyToastRef.current = true;
      toast.success("Scan completed successfully!");
    } else if (statusData.status === "Failed" && !hasShownReportReadyToastRef.current) {
      hasShownReportReadyToastRef.current = true;
      toast.error("Scan failed");
    } else if (statusData.filesReceived && !hasShownReportReadyToastRef.current) {
      hasShownReportReadyToastRef.current = true;
      toast.success("Report is ready to view!");
    }
    
    // Always update the current scan data with the latest information
    if (statusData.web_session_id && currentScan) {
      // Update current scan with session ID and file IDs
      setCurrentScan({
        ...currentScan,
        session_id: statusData.web_session_id,
        fileIds: statusData.fileIds,
        status: statusData.status || currentScan.status
      });
      
      // Store session ID in cookie
      if (statusData.web_session_id) {
        Cookies.set('session_id', statusData.web_session_id, { expires: 30 }); // 30 days
      }
      
      // Update scan history in localStorage
      const scanHistory = JSON.parse(localStorage.getItem("scanHistory") || "[]");
      const updatedHistory = scanHistory.map(scan => {
        if (scan.task_id === currentScan.task_id) {
          return {
            ...scan,
            session_id: statusData.web_session_id,
            fileIds: statusData.fileIds,
            status: statusData.status || scan.status
          };
        }
        return scan;
      });
      localStorage.setItem("scanHistory", JSON.stringify(updatedHistory));
    }
  };
  
  const handleNewScan = () => {
    // Clear current scan
    setCurrentScan(null);
    
    // Reset toast flags
    hasShownReportReadyToastRef.current = false;
  };

  return (
    <div className="zap-home">
      <div className="zap-tagline">Uncover the Shadows. Test. Secure. Repeat.</div>
      
      <div className="zap-container">
        {currentScan ? (
          <>
            <div className="zap-current-scan">
              <div className="zap-scan-header">
                <h2>Current Scan</h2>
                <button 
                  onClick={handleNewScan}
                  className="zap-button zap-button-small"
                  style={{ padding: '4px 10px', fontSize: '13px', minWidth: '80px' }}
                >
                  New Scan
                </button>
              </div>
              <div className="zap-scan-details">
                <div className="zap-scan-target">
                  <strong>Target:</strong> {currentScan.target_url}
                </div>
                <div className="zap-scan-info">
                  <span><strong>Type:</strong> {currentScan.scan_type}</span>
                  <span><strong>Report:</strong> {currentScan.report_type}</span>
                  <span><strong>Format:</strong> {currentScan.report_format}</span>
                </div>
              </div>
              
              <RealtimeStatus 
                key={`scan-${scanKey}`} // Add key to force remounting
                taskId={currentScan.task_id} 
                onStatusUpdate={handleStatusUpdate}
              />
            </div>
          </>
        ) : (
          <ScanForm onScanComplete={handleScanComplete} />
        )}
      </div>
    </div>
  );
};

export default HomePage; 