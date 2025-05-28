# Test script to examine the output of the llama_service's analyze_vulnerabilities function
import os
import sys
import json
from pathlib import Path

# This adds the project root to the Python path to allow importing app modules
sys.path.append(str(Path(__file__).parent))

from app.services.llama_service import analyze_vulnerabilities


def test_read_zap_output(scan_type, timestamp):
    zap_folder = os.path.join('reports', 'zap_outputs', f"{scan_type}-scan_{timestamp}")
    xml_reports = [] 
    for root, dirs, files in os.walk(zap_folder):
        for file in files:
            if file.endswith('.xml'):
                xml_reports.append(os.path.join(root, file))
    
    if not xml_reports:
        print("No XML reports found in the reports directory.")
        return
    
    # Sort by modification time (newest first)
    xml_reports.sort(key=os.path.getmtime, reverse=True)
    latest_report = xml_reports[0]
    
    print(f"\nAnalyzing the most recent XML report: {latest_report}\n")
    print("-" * 80)
    
    # Call the analyze_vulnerabilities function
    try:
        result = analyze_vulnerabilities(latest_report)
        
        # Check if the analysis was successful
        if result.get("success", False):
            # Print the AI-enhanced report
            print("\n=== AI-ENHANCED VULNERABILITY REPORT ===\n")
            print(result["response"])
            
            # Print raw vulnerability data for comparison
            print("\n=== RAW VULNERABILITY DATA ===\n")
            vulnerabilities = result.get("vulnerabilities", [])
            print(f"Found {len(vulnerabilities)} vulnerabilities")
            
            # Print a sample of the raw data for comparison
            if vulnerabilities:
                print("\nSample of raw vulnerability data (first vulnerability):")
                print(json.dumps(vulnerabilities[0], indent=2))
        else:
            print(f"Analysis failed: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    # Example values; replace with actual scan_type and timestamp as needed
    test_read_zap_output("basic", "20250528_161544")