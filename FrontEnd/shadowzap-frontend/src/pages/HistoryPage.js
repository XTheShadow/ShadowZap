import React from "react";
import ScanHistory from "../components/ScanHistory";

const HistoryPage = () => {
  return (
    <div className="zap-history-page">
      <h1>Scan History</h1>
      <div className="zap-container">
        <ScanHistory />
      </div>
    </div>
  );
};

export default HistoryPage; 