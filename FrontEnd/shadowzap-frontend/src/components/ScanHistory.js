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

const ScanHistory = () => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionFiles, setSessionFiles] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const initialLoadRef = useRef(true);
  const isManualRefreshRef = useRef(false);
  const loadingTimeoutRef = useRef(null);
  const userSessionId = Cookies.get('session_id'); // Get current user's session ID

  // Load sessions from API
  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true);
      
      // Set a timeout to ensure loading state doesn't get stuck
      loadingTimeoutRef.current = setTimeout(() => {
        if (loading) {
          console.log("History data fetch timeout - using local data");
          // Try to use local storage data as fallback
          try {
            const localSessions = JSON.parse(localStorage.getItem("scanHistory") || "[]");
            
            // Filter by user session if available
            const userSessions = userSessionId 
              ? localSessions.filter(scan => scan.session_id === userSessionId)
              : localSessions;
              
            setSessions(userSessions);
          } catch (e) {
            console.error("Error loading local session data:", e);
          }
          setLoading(false);
        }
      }, 10000); // 10 seconds timeout
      
      // Get sessions data with session filter if available
      let endpoint = `${API_URL}/sessions`;
      if (userSessionId) {
        endpoint = `${API_URL}/sessions?session_id=${userSessionId}`;
      }
      
      const sessionsResponse = await safeApiCall(endpoint);
      
      // If endpoint doesn't exist or returns error, handle gracefully
      if (sessionsResponse.status === 404 || !sessionsResponse.data) {
        // Try to use local storage data instead
        const localSessions = JSON.parse(localStorage.getItem("scanHistory") || "[]");
        
        // Filter by user session if available
        const userSessions = userSessionId 
          ? localSessions.filter(scan => scan.session_id === userSessionId)
          : localSessions;
          
        setSessions(userSessions);
        setLoading(false);
        
        // Clear timeout
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
          loadingTimeoutRef.current = null;
        }
        return;
      }
      
      if (sessionsResponse.data && Array.isArray(sessionsResponse.data)) {
        // Get session data
        const sessionData = sessionsResponse.data;
        
        // For each session, check if there's a scan status we need to fetch
        const enhancedSessions = await Promise.all(
          sessionData.map(async (session) => {
            // Try to get the task_id from the session
            let taskId = session.task_id;
            
            // If no task_id directly in session, try to find it in the database
            if (!taskId) {
              try {
                // Try to find a scan with this web_session_id
                const scanResponse = await safeApiCall(`${API_URL}/scan-by-session/${session.session_id}`);
                if (scanResponse.status !== 404 && scanResponse.data && scanResponse.data.task_id) {
                  taskId = scanResponse.data.task_id;
                  session.task_id = taskId;
                }
              } catch (error) {
                console.error(`Error fetching scan for session ${session.session_id}:`, error);
              }
            }
            
            // If we have a task_id, fetch its status
            if (taskId) {
              try {
                const statusResponse = await safeApiCall(`${API_URL}/scan/${taskId}`);
                if (statusResponse.status !== 404 && statusResponse.data && statusResponse.data.status) {
                  return {
                    ...session,
                    status: statusResponse.data.status
                  };
                }
              } catch (error) {
                console.error(`Error fetching status for task ${taskId}:`, error);
              }
            }
            
            // If we couldn't get a status, try to infer it from the session data
            if (session.file_count && session.file_count > 0) {
              return {
                ...session,
                status: "Completed"
              };
            }
            
            return session;
          })
        );
        
        // Sort sessions by timestamp (newest first)
        const sortedSessions = enhancedSessions.sort((a, b) => {
          return new Date(b.timestamp) - new Date(a.timestamp);
        });
        
        setSessions(sortedSessions);
        
        // Only show toast for manual refresh
        if (isManualRefreshRef.current) {
          toast.success("Scan history updated");
          isManualRefreshRef.current = false;
        }
      } else if (isManualRefreshRef.current) {
        // Only show toast for manual refresh
        toast.info("No scan history available");
        isManualRefreshRef.current = false;
      }
    } catch (error) {
      console.error("Error fetching sessions:", error);
      
      // Only show error toast for manual refresh
      if (isManualRefreshRef.current) {
        toast.error("Error loading scan history");
        isManualRefreshRef.current = false;
      }
      
      // Try to use local storage data as fallback
      try {
        const localSessions = JSON.parse(localStorage.getItem("scanHistory") || "[]");
        
        // Filter by user session if available
        const userSessions = userSessionId 
          ? localSessions.filter(scan => scan.session_id === userSessionId)
          : localSessions;
          
        setSessions(userSessions);
      } catch (e) {
        console.error("Error loading local session data:", e);
      }
    } finally {
      // Always set loading to false when done
      setLoading(false);
      initialLoadRef.current = false;
      
      // Clear any loading timeout
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
        loadingTimeoutRef.current = null;
      }
    }
  }, [userSessionId, loading]);
  
  // Initial load and manual refresh
  useEffect(() => {
    // Only fetch data if this is the initial load or a manual refresh
    if (initialLoadRef.current || refreshKey > 0) {
      fetchSessions();
    }
    
    // Clean up timeout on unmount
    return () => {
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
        loadingTimeoutRef.current = null;
      }
    };
  }, [refreshKey, fetchSessions]);

  const handleRefresh = () => {
    // Don't allow refresh if already loading
    if (loading) return;
    
    // Manual refresh - increment the key to trigger the effect
    setRefreshKey(oldKey => oldKey + 1);
    isManualRefreshRef.current = true;
    toast.info("Refreshing scan history...");
  };

  const viewSessionFiles = async (session) => {
    setSelectedSession(session);
    
    try {
      const response = await safeApiCall(`${API_URL}/sessions/${session.session_id}/files`);
      
      // If endpoint doesn't exist or returns error, handle gracefully
      if (response.status === 404 || !response.data) {
        setSessionFiles([]);
        toast.info("No files found for this scan - API endpoint not available");
        return;
      }
      
      if (response.data && Array.isArray(response.data)) {
        // Filter to only include downloadable files
        const downloadableFiles = response.data.map(group => ({
          ...group,
          files: group.files.filter(file => 
            file.filename && 
            (file.filename.endsWith('.pdf') || 
             file.filename.endsWith('.html') || 
             file.filename.endsWith('.xml') || 
             file.filename.endsWith('.json'))
          )
        })).filter(group => group.files.length > 0);
        
        // The API returns groups of files
        setSessionFiles(downloadableFiles);
        
        // Count total files
        const totalFiles = downloadableFiles.reduce((count, group) => count + group.files.length, 0);
        
        if (totalFiles === 0) {
          toast.info("No downloadable report files found for this scan");
        } else if (totalFiles > 0) {
          // Only show toast when files are found
          toast.success(`Found ${totalFiles} downloadable files`);
        }
      } else {
        setSessionFiles([]);
        toast.info("No files found for this scan");
      }
    } catch (error) {
      console.error("Error fetching session files:", error);
      toast.error("Error loading scan files");
      setSessionFiles([]);
    }
  };
  
  const openFile = (fileId) => {
    window.open(`${API_URL}/files/${fileId}`, '_blank');
  };
  
  const getFileTypeLabel = (filename) => {
    if (filename.toLowerCase().endsWith('.pdf')) return 'PDF Report';
    if (filename.toLowerCase().endsWith('.xml')) return 'XML Report';
    if (filename.toLowerCase().endsWith('.json')) return 'JSON Report';
    if (filename.toLowerCase().endsWith('.html')) return 'HTML Report';
    return filename;
  };

  const getFileTypeIcon = (filename) => {
    if (filename.toLowerCase().endsWith('.pdf')) return '📄';
    if (filename.toLowerCase().endsWith('.xml')) return '🔧';
    if (filename.toLowerCase().endsWith('.json')) return '📊';
    if (filename.toLowerCase().endsWith('.html')) return '🌐';
    return '📁';
  };

  const formatDate = (dateString) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch (e) {
      return "Unknown date";
    }
  };

  const getStatusClass = (status) => {
    if (!status) return "";
    
    status = status.toLowerCase();
    
    if (status === "completed" || status === "success" || status === "finished") {
      return "zap-status-success";
    }
    
    if (status === "failed" || status === "error" || status === "failure") {
      return "zap-status-error";
    }
    
    if (status === "running" || status === "in progress" || status === "scanning") {
      return "zap-status-running";
    }
    
    if (status === "initializing" || status === "pending") {
      return "zap-status-pending";
    }
    
    return "zap-status-pending";
  };

  return (
    <div className="zap-history">
      <div className="zap-history-header">
        <h2>Scan History</h2>
        <button 
          onClick={handleRefresh} 
          className="zap-refresh-button"
          disabled={loading}
          title="Refresh scan history and check for status updates"
        >
          {loading ? "Refreshing..." : "Refresh History"}
        </button>
      </div>
      
      {loading && sessions.length === 0 ? (
        <div className="zap-loading">Loading scan history...</div>
      ) : sessions.length === 0 ? (
        <p className="zap-no-history">No scan history available</p>
      ) : (
        <div className="zap-history-list">
          {sessions.map((session, index) => (
            <div key={index} className="zap-history-item">
              <div className="zap-history-info">
                <div className="zap-history-target">{session.target_url}</div>
                <div className="zap-history-details">
                  <span className="zap-history-type">{session.scan_type}</span>
                  <span className={`zap-history-status ${getStatusClass(session.status)}`}>
                    {session.status || "Unknown"}
                  </span>
                  <span className="zap-history-date">{formatDate(session.timestamp)}</span>
                  <span className="zap-history-files">{session.file_count || 0} files</span>
                </div>
              </div>
              <div className="zap-history-actions">
                <button 
                  onClick={() => viewSessionFiles(session)} 
                  className="zap-history-button zap-button-small"
                >
                  View Files
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {selectedSession && (
        <div className="zap-session-details">
          <h3>Scan Reports for {selectedSession.target_url}</h3>
          
          {sessionFiles.length === 0 ? (
            <p>No downloadable report files available</p>
          ) : (
            <div className="zap-file-grid">
              {sessionFiles.map((group, index) => (
                <div key={index} className="zap-file-group">
                  <h4 className="zap-file-group-header">{formatDate(group.timestamp)}</h4>
                  <div className="zap-file-cards">
                    {group.files.map((file, fileIndex) => (
                      <div key={fileIndex} className="zap-file-card">
                        <div className="zap-file-icon">
                          {getFileTypeIcon(file.filename)}
                        </div>
                        <div className="zap-file-info">
                          <div className="zap-file-name">{getFileTypeLabel(file.filename)}</div>
                          <div className="zap-file-date">{formatDate(file.upload_date)}</div>
                        </div>
                        <button 
                          onClick={() => openFile(file.file_id)} 
                          className="zap-file-button"
                          title="Download or view this file"
                        >
                          Download
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          
          <button 
            onClick={() => {
              setSelectedSession(null);
            }} 
            className="zap-button zap-button-small"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
};

export default ScanHistory; 