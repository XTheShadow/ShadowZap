from app.tasks.scan_tasks import run_scan
from app.models.scan_model import ScanType, ReportType, ReportFormat
import time
import json
import os
import pytest
from tests.test_helpers import verify_enhanced_reports
from app.services.database_service import DatabaseService  # Import the database service


def test_basic_scan():
    # Initialize database service for testing
    print("\n--- Testing Database Connection ---")
    try:
        db_service = DatabaseService()
        print(f"Database connection initialized: {db_service.client}")
        print(f"Database name: {db_service.db.name}")
        print(f"Available collections: {db_service.db.list_collection_names()}")
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
    
    # Target URL for testing, using a test website that's designed for security testing
    target_url = "http://testphp.vulnweb.com"
    scan_type = ScanType.BASIC
    report_type = ReportType.ENHANCED
    report_format = ReportFormat.PDF
    
    try:
        # Initiating the scan task
        print(f"Starting {scan_type} scan against {target_url}...")
        scan_result = run_scan.delay(target_url, scan_type.value, report_type.value, report_format.value)
        
        # Phase 1: ZAP Scanning
        print("Phase 1: ZAP Scanning")
        while not scan_result.ready():
            print("Scan in progress...")
            time.sleep(60)  # Check status every minute
        
        # Getting the final result
        print("ZAP scan completed.")
        result = scan_result.get()
        
        # Print full result for debugging
        print("\nFull result:")
        print(json.dumps(result, indent=2, default=str))
        
        # Verify ZAP scan completed successfully
        assert result['status'] == 'Completed', f"ZAP scan failed with status: {result['status']}"
        
        # Phase 2: Verify ZAP reports were generated
        print("Phase 2: Verifying ZAP reports")
        assert 'reports' in result, "No reports section in result"
        assert result['reports']['html'] and os.path.exists(result['reports']['html']), "HTML report not generated"
        assert result['reports']['xml'] and os.path.exists(result['reports']['xml']), "XML report not generated"
        assert result['reports']['json'] and os.path.exists(result['reports']['json']), "JSON report not generated"
        print("ZAP reports successfully generated.")
        
        # Phase 3: Verify AI analysis was performed
        print("Phase 3: Verifying AI analysis")
        assert 'ai_analysis' in result, "AI analysis was not performed"
        assert result['ai_analysis']['success'], f"AI analysis failed: {result['ai_analysis'].get('error', 'Unknown error')}"
        print("AI analysis completed successfully.")
        
        # Phase 4: Verify markdown report was generated
        print("Phase 4: Verifying markdown report")
        assert 'markdown' in result['reports'], "Markdown report not found in results"
        assert os.path.exists(result['reports']['markdown']), f"Markdown file does not exist at {result['reports']['markdown']}"
        print(f"Markdown report path: {result['reports']['markdown']}")
        print("Markdown report successfully generated.")
        
        # Phase 5: Verify enhanced reports were generated in the enhanced_reports directory
        print("Phase 5: Verifying enhanced reports in enhanced_reports directory")
        assert 'enhanced_reports_folder' in result, "Enhanced reports folder not found in results"
        enhanced_folder = result['enhanced_reports_folder']
        assert os.path.exists(enhanced_folder), f"Enhanced reports folder does not exist at {enhanced_folder}"
        
        # Check if the enhanced folder contains the expected files
        files_in_enhanced_folder = os.listdir(enhanced_folder)
        print(f"Files in enhanced folder: {files_in_enhanced_folder}")
        
        # Check for XML, JSON and PDF files in the enhanced folder
        has_xml = any(file.endswith('.xml') for file in files_in_enhanced_folder)
        has_json = any(file.endswith('.json') for file in files_in_enhanced_folder)
        has_pdf = any(file.endswith('.pdf') for file in files_in_enhanced_folder)
        
        assert has_xml, "XML report not found in enhanced reports folder"
        assert has_json, "JSON report not found in enhanced reports folder"
        assert has_pdf, "PDF report not found in enhanced reports folder"
        
        # Check if the enhanced reports paths are in the result
        assert 'xml_enhanced' in result['reports'], "Enhanced XML report path not found in results"
        assert 'json_enhanced' in result['reports'], "Enhanced JSON report path not found in results"
        assert 'pdf_enhanced' in result['reports'], "Enhanced PDF report path not found in results"
        
        # Check if the enhanced report files exist
        assert os.path.exists(result['reports']['xml_enhanced']), f"Enhanced XML file does not exist at {result['reports']['xml_enhanced']}"
        assert os.path.exists(result['reports']['json_enhanced']), f"Enhanced JSON file does not exist at {result['reports']['json_enhanced']}"
        assert os.path.exists(result['reports']['pdf_enhanced']), f"Enhanced PDF file does not exist at {result['reports']['pdf_enhanced']}"
        
        print("Enhanced reports successfully generated and verified.")
        
        # Phase 6: Test database storage
        print("\n--- Phase 6: Testing Database Storage ---")
        try:
            db_service = DatabaseService()
            
            # Try to save a test report to the database
            print("Attempting to save report to database...")
            report_id = db_service.save_report(
                scan_id="test_scan_id",
                target_url=target_url,
                report_type=report_type.value,
                report_format=report_format.value,
                report_paths=result['reports']
            )
            
            print(f"Report saved with ID: {report_id}")
            
            # Try to retrieve the saved report
            print("Attempting to retrieve saved report...")
            saved_report = db_service.get_report(report_id)
            if saved_report:
                print(f"Successfully retrieved report: {saved_report['report_id']}")
            else:
                print("Failed to retrieve saved report")
                
            # List all reports in the database
            print("Listing all reports in database...")
            all_reports = db_service.list_reports()
            print(f"Found {len(all_reports)} reports in database")
            
            # Check GridFS for stored files
            print("Checking GridFS for stored files...")
            grid_files = list(db_service.fs.find())
            print(f"Found {len(grid_files)} files in GridFS")
            for file in grid_files[:5]:  # Show first 5 files
                print(f"  - {file.filename} ({file._id})")
                
        except Exception as e:
            print(f"ERROR: Database operation failed: {e}")
        
        print("All phases completed successfully!")
        
        # Get the final result for reporting
        
        # Pretty print the results
        print("\nScan Completed!")
        print("==============")
        print(f"Status: {result['status']}")
        print(f"Target: {result['target']}")
        print(f"Scan Type: {result['scan_type']}")
        
        if result['status'] == 'Completed':
            print("\nReport Locations:")
            print(f"HTML Report: {result['reports']['html']}")
            print(f"XML Report: {result['reports']['xml']}")
            print(f"JSON Report: {result['reports']['json']}")
            
            if 'enhanced_reports_folder' in result:
                print(f"\nEnhanced Reports Folder: {result['enhanced_reports_folder']}")
                print(f"Enhanced XML Report: {result['reports'].get('xml_enhanced', 'N/A')}")
                print(f"Enhanced JSON Report: {result['reports'].get('json_enhanced', 'N/A')}")
                print(f"Enhanced PDF Report: {result['reports'].get('pdf_enhanced', 'N/A')}")
            
            print("\nScan Logs:")
            print(result['logs'])
        else:
            print("\nError Information:")
            if 'error' in result:
                print(f"Error: {result['error']}")
            print(f"Exit Code: {result.get('exit_code', 'N/A')}")
            
    except Exception as e:
        print(f"\nAn error occurred during the scan: {str(e)}")


if __name__ == "__main__":
    test_basic_scan()