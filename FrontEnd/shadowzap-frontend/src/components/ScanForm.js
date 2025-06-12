import React, { useState, useEffect } from "react";
import { toast } from "react-toastify";
import axios from "axios";
import Cookies from 'js-cookie';

const API_URL = "http://127.0.0.1:8000";

const ScanForm = ({ onScanComplete }) => {
  const [url, setUrl] = useState("");
  const [scanType, setScanType] = useState("basic");
  const [reportType, setReportType] = useState("enhanced");
  const [reportFormat] = useState("pdf");
  const [scanning, setScanning] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  // Get session ID on component mount
  useEffect(() => {
    const currentSessionId = Cookies.get('session_id');
    if (currentSessionId) {
      setSessionId(currentSessionId);
    }
  }, []);

  const handleScan = async (e) => {
    e.preventDefault();
    
    if (!url) {
      toast.error("Please enter a target URL");
      return;
    }
    
    // Validate URL format
    try {
      new URL(url);
    } catch (error) {
      toast.error("Please enter a valid URL (including http:// or https://)");
      return;
    }
    
    setScanning(true);
    
    try {
      // Notify parent immediately that we're starting a new scan
      if (onScanComplete) {
        onScanComplete({
          target_url: url,
          scan_type: scanType,
          report_type: reportType,
          report_format: reportFormat,
          status: "Initializing",
          timestamp: new Date().toISOString(),
          task_id: null // Will be updated when API responds
        });
      }
      
      // Include session ID in the request if available
      const requestData = {
        target_url: url,
        scan_type: scanType,
        report_type: reportType,
        report_format: reportFormat
      };
      
      if (sessionId) {
        requestData.session_id = sessionId;
      }
      
      const response = await axios.post(`${API_URL}/scan`, requestData);
      
      // If we get a session ID in the response, save it
      if (response.data && response.data.web_session_id) {
        Cookies.set('session_id', response.data.web_session_id, { expires: 30 }); // 30 days expiry
        setSessionId(response.data.web_session_id);
      }
      
      toast.success("Scan initiated successfully");
      
      // Pass the scan data to parent component with API response
      if (onScanComplete) {
        onScanComplete({
          ...response.data,
          timestamp: new Date().toISOString(),
          target_url: url,
          scan_type: scanType,
          report_type: reportType,
          report_format: reportFormat,
          status: "Initializing"
        });
      }
    } catch (error) {
      console.error("Scan error:", error);
      toast.error(error.response?.data?.detail || "Error starting scan");
      
      // Notify parent of failure
      if (onScanComplete) {
        onScanComplete({
          target_url: url,
          scan_type: scanType,
          report_type: reportType,
          report_format: reportFormat,
          status: "Failed",
          error: error.response?.data?.detail || "Error starting scan",
          timestamp: new Date().toISOString()
        });
      }
    } finally {
      setScanning(false);
    }
  };

  return (
    <form onSubmit={handleScan} className="zap-form">
      <input
        type="text"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        className="zap-input"
        placeholder="https://target-site.com"
      />

      <div className="zap-options">
        <select value={scanType} onChange={(e) => setScanType(e.target.value)}>
          <option value="basic">Basic Scan</option>
          <option value="full">Full Scan</option>
          <option value="api_scan">API Scan</option>
          <option value="spider_scan">Spider Scan</option>
        </select>

        <select value={reportType} onChange={(e) => setReportType(e.target.value)}>
          <option value="normal">Normal</option>
          <option value="enhanced">Enhanced (AI)</option>
        </select>
      </div>

      <button 
        type="submit" 
        className="zap-button" 
        disabled={scanning}
      >
        🔥 {scanning ? "Scanning..." : "Start Scan"}
      </button>
    </form>
  );
};

export default ScanForm; 