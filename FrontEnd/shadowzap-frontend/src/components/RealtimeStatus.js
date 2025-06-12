import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import Cookies from 'js-cookie'; // For cookie management

const API_URL = "http://127.0.0.1:8000";

// Helper function to safely make API calls
const safeApiCall = async (url, method = 'get', data = null) => {
  try {
    const config = { validateStatus: status => status < 500 };
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

const RealtimeStatus = ({ taskId, onStatusUpdate }) => {
  const [status, setStatus] = useState("Initializing");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [completed, setCompleted] = useState(false);
  const [fileIds, setFileIds] = useState({});
  const [sessionId, setSessionId] = useState(null);
  const [reportId, setReportId] = useState(null);
  const [reportType, setReportType] = useState(null);
  const [debugInfo, setDebugInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const prevStatusRef = useRef("Initializing");
  const hasNotifiedCompletionRef = useRef(false);
  const hasNotifiedFilesRef = useRef(false);

  // Get session ID when component mounts
  useEffect(() => {
    // Try to get existing session ID from cookie
    let existingSessionId = Cookies.get('session_id');
    
    if (!existingSessionId) {
      // If no session ID exists, we'll get one from the server when we make our first request
      console.log("No existing session ID found");
    } else {
      console.log("Found existing session ID:", existingSessionId);
      setSessionId(existingSessionId);
    }
  }, []);

  // Reset state when taskId changes
  useEffect(() => {
    // Only proceed if we have a valid taskId
    if (!taskId) return;
    
    setStatus("Initializing");
    setProgress(0);
    setError(null);
    setCompleted(false);
    setFileIds({});
    setReportId(null);
    setReportType(null);
    setDebugInfo(null);
    prevStatusRef.current = "Initializing";
    hasNotifiedCompletionRef.current = false;
    hasNotifiedFilesRef.current = false;
    
    // Initial status check when task ID is set
    checkStatus();
  }, [taskId]);

  // Check status when refresh key changes
  useEffect(() => {
    if (taskId && refreshKey > 0) {
      checkStatus();
    }
  }, [refreshKey]);

  // Add automatic refresh every 5 seconds
  useEffect(() => {
    // Only set up automatic refresh if we have a taskId and the scan is not completed
    if (taskId && !completed) {
      console.log("Setting up automatic refresh interval");
      const intervalId = setInterval(() => {
        // Only refresh if not currently loading
        if (!loading) {
          console.log("Auto-refreshing scan status");
          setRefreshKey(prevKey => prevKey + 1);
        }
      }, 5000); // 5 seconds interval
      
      // Clean up interval on unmount or when scan completes
      return () => {
        console.log("Clearing automatic refresh interval");
        clearInterval(intervalId);
      };
    }
  }, [taskId, completed, loading]);

  const checkStatus = async () => {
    // Don't proceed if we don't have a taskId
    if (!taskId) {
      console.log("No task ID available, skipping status check");
      return;
    }
    
    // Don't allow multiple simultaneous status checks
    if (loading) return;
    
    setLoading(true);
    
    try {
      // Include session ID in the request if available
      let endpoint = `${API_URL}/scan/${taskId}`;
      if (sessionId) {
        endpoint += `?session_id=${sessionId}`;
      }
      
      const response = await safeApiCall(endpoint);
      
      // If endpoint doesn't exist or returns error, handle gracefully
      if (response.status === 404 || !response.data) {
        console.log("Scan status endpoint not available");
        setProgress(prev => Math.min(prev + 5, 100)); // Still show some progress
        if (progress >= 100) {
          setCompleted(true);
          setStatus("Completed");
        }
        setLoading(false);
        return;
      }
      
      const data = response.data;
      
      console.log("Scan status response:", data);
      setDebugInfo(JSON.stringify(data, null, 2));
      
      // Update status
      if (data.status) {
        // Only notify if status has changed to something meaningful
        const newStatus = data.status;
        if (newStatus !== prevStatusRef.current) {
          prevStatusRef.current = newStatus;
          
          // Don't notify about initializing status
          if (newStatus !== "Initializing" && onStatusUpdate) {
            // Notify parent of status change for important status changes
            if (["Running", "Processing", "Completed", "Failed"].includes(newStatus)) {
              onStatusUpdate({
                ...data,
                fileIds: data.gridfs_file_ids,
                web_session_id: data.web_session_id || sessionId,
                reportId: data.report_id,
                reportType: data.report_type
              });
            }
          }
        }
        
        setStatus(data.status);
        
        // Store file IDs and session ID if available
        if (data.gridfs_file_ids && Object.keys(data.gridfs_file_ids).length > 0) {
          // Only notify about files once
          if (!hasNotifiedFilesRef.current && Object.keys(fileIds).length === 0) {
            hasNotifiedFilesRef.current = true;
            console.log("File IDs received:", data.gridfs_file_ids);
            
            // Notify parent about files
            if (onStatusUpdate) {
              onStatusUpdate({
                ...data,
                fileIds: data.gridfs_file_ids,
                web_session_id: data.web_session_id || sessionId,
                reportId: data.report_id,
                reportType: data.report_type,
                filesReceived: true
              });
            }
          }
          
          setFileIds(data.gridfs_file_ids);
        }
        
        if (data.web_session_id) {
          setSessionId(data.web_session_id);
          // Store session ID in cookie for persistence
          Cookies.set('session_id', data.web_session_id, { expires: 30 }); // 30 days expiry
          
          // Trigger a dashboard update when we get a session ID - but check if endpoint exists first
          try {
            const dashboardCheck = await safeApiCall(`${API_URL}/dashboard`, 'get');
            if (dashboardCheck.status !== 404) {
              await safeApiCall(`${API_URL}/update-dashboard`, 'post', { 
                session_id: data.web_session_id,
                task_id: taskId
              });
            }
          } catch (error) {
            console.log("Error updating dashboard:", error);
          }
        }
        
        if (data.report_id) {
          setReportId(data.report_id);
        }
        
        // Store report type if available
        if (data.report_type) {
          setReportType(data.report_type);
        }
        
        // Set completion based on status or explicit completed flag
        if ((["Completed", "Failed"].includes(data.status) || data.completed === true) && !completed) {
          setCompleted(true);
          
          // Notify about completion only once
          if (!hasNotifiedCompletionRef.current) {
            hasNotifiedCompletionRef.current = true;
            
            // When scan completes, update dashboard and history - but check if endpoint exists first
            if (data.web_session_id || sessionId) {
              try {
                const dashboardCheck = await safeApiCall(`${API_URL}/dashboard`, 'get');
                if (dashboardCheck.status !== 404) {
                  await safeApiCall(`${API_URL}/update-dashboard`, 'post', { 
                    session_id: data.web_session_id || sessionId,
                    task_id: taskId,
                    status: data.status
                  });
                }
              } catch (error) {
                console.log("Error updating dashboard on completion:", error);
              }
            }
          }
        }
      }
      
      // Calculate progress based on status
      switch(data.status) {
        case "Initializing":
          setProgress(10);
          break;
        case "Running":
          setProgress(50);
          break;
        case "Processing":
          setProgress(75);
          break;
        case "Completed":
          setProgress(100);
          setCompleted(true);
          break;
        case "Failed":
          setProgress(100);
          setError(data.error || "Scan failed");
          setCompleted(true);
          break;
        default:
          setProgress(25);
      }
      
      // Force completion if we have report files
      if (data.gridfs_file_ids && Object.keys(data.gridfs_file_ids).length > 0) {
        console.log("Forcing completion because report files are available");
        setProgress(100);
        setCompleted(true);
        if (data.status === "Initializing" || data.status === "Pending") {
          setStatus("Completed");
        }
      }
    } catch (error) {
      console.error("Error checking scan status:", error);
      setError("Error checking scan status");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    // Don't allow refresh if already loading
    if (loading) return;
    
    // Don't allow refresh if we don't have a taskId
    if (!taskId) {
      console.log("No task ID available, cannot refresh status");
      return;
    }
    
    // Manual refresh - increment the key to trigger the effect
    setRefreshKey(prevKey => prevKey + 1);
  };

  const openReport = (fileId) => {
    window.open(`${API_URL}/files/${fileId}`, '_blank');
  };

  // Function to open the enhanced HTML report directly
  const openEnhancedHtmlReport = () => {
    // If we have session ID, we can use that to access the latest enhanced HTML report
    if (sessionId) {
      // Construct the path to the enhanced HTML report using session ID
      window.open(`${API_URL}/session-reports/${sessionId}/enhanced-html`, '_blank');
    } else if (reportId) {
      // Fallback to report ID if session ID is not available
      window.open(`${API_URL}/enhanced-html/${reportId}`, '_blank');
    } else {
      alert("Enhanced HTML report is not available");
    }
  };
  
  // Function to open the enhanced PDF report directly
  const openEnhancedPdfReport = () => {
    // If we have session ID, we can use that to access the latest enhanced PDF report
    if (sessionId) {
      // Construct the path to the enhanced PDF report using session ID
      window.open(`${API_URL}/session-reports/${sessionId}/enhanced-pdf`, '_blank');
    } else if (reportId) {
      // Use the PDF file ID if available
      if (fileIds.pdf_enhanced) {
        openReport(fileIds.pdf_enhanced);
      } else {
        alert("Enhanced PDF report is not available");
      }
    } else {
      alert("Enhanced PDF report is not available");
    }
  };

  // Determine which report buttons to show based on report type
  const renderReportButtons = () => {
    const isEnhanced = reportType === 'enhanced';
    
    return (
      <div className="zap-button-group">
        {/* For Normal reports: HTML, XML, JSON */}
        {!isEnhanced && fileIds.html && (
          <button 
            className="zap-button zap-button-small" 
            onClick={() => openReport(fileIds.html)}
          >
            HTML Report
          </button>
        )}
        
        {/* For Enhanced reports: PDF, XML, JSON And HTML to show */}
        {isEnhanced && fileIds.pdf_enhanced && (
          <button 
            className="zap-button zap-button-small" 
            onClick={() => openReport(fileIds.pdf_enhanced)}
          >
            Enhanced PDF
          </button>
        )}
        
        {/* Enhanced HTML report button */}
        {isEnhanced && (sessionId || reportId) && (
          <button 
            className="zap-button zap-button-small" 
            onClick={openEnhancedHtmlReport}
          >
            Enhanced HTML
          </button>
        )}
        
        {/* Enhanced PDF direct download button */}
        {isEnhanced && (sessionId || reportId) && (
          <button 
            className="zap-button zap-button-small" 
            onClick={openEnhancedPdfReport}
          >
            Download PDF
          </button>
        )}
        
        {/* Always show XML and JSON for both report types */}
        {fileIds.json && (
          <button 
            className="zap-button zap-button-small" 
            onClick={() => openReport(isEnhanced && fileIds.json_enhanced ? fileIds.json_enhanced : fileIds.json)}
          >
            JSON Report
          </button>
        )}
        
        {fileIds.xml && (
          <button 
            className="zap-button zap-button-small" 
            onClick={() => openReport(isEnhanced && fileIds.xml_enhanced ? fileIds.xml_enhanced : fileIds.xml)}
          >
            XML Report
          </button>
        )}
      </div>
    );
  };

  // If no taskId is provided, show a message
  if (!taskId) {
    return (
      <div className="zap-realtime-status">
        <div className="zap-warning-message">
          No scan task ID available. Please start a new scan.
        </div>
      </div>
    );
  }

  return (
    <div className="zap-realtime-status">
      <div className="zap-status-header">
        <h3>Scan Status: {status}</h3>
      </div>
      
      <div className="zap-progress-container">
        <div 
          className={`zap-progress-bar ${error ? 'zap-progress-error' : ''}`}
          style={{ width: `${progress}%` }}
        ></div>
      </div>
      
      {error && (
        <div className="zap-error-message">{error}</div>
      )}
      
      {completed && !error && (
        <div className="zap-success-message">
          Scan completed successfully!
          
          {Object.keys(fileIds).length > 0 ? (
            <div className="zap-report-links">
              <p>View reports ({reportType === 'enhanced' ? 'Enhanced' : 'Normal'}):</p>
              {renderReportButtons()}
              
              {reportId && (
                <p className="zap-session-info">
                  Report ID: <span className="zap-session-id">{reportId}</span>
                </p>
              )}
            </div>
          ) : (
            <div className="zap-warning-message">
              <p>No report files available. This might be because:</p>
              <ul>
                <li>The scan didn't generate any reports</li>
                <li>The reports weren't properly saved to the database</li>
                <li>There was an issue retrieving the file IDs</li>
              </ul>
              <p>Check the server logs for more information.</p>
              
              {debugInfo && (
                <details>
                  <summary>Debug Information</summary>
                  <pre className="zap-debug-info">{debugInfo}</pre>
                </details>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RealtimeStatus; 