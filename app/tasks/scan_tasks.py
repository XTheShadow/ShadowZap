# This file is for handling the Celery tasks.
from ..services.celery_service import celery # Importing the celery instance from celery_service
from pydantic import AnyHttpUrl
from ..models.scan_model import ScanType, ReportType, ReportFormat
from typing import List # A pyton library that introduces a new data type called List
import docker
import datetime
import os
import shutil # Used to copy files
from dotenv import load_dotenv # Used to import from the .env file
from ..services.llama_service import analyze_vulnerabilities
from ..utils.visuals_enhancer import enhance_report
from ..services.database_service import DatabaseService # Importing the DatabaseService class from the database_service.py file
from bson.objectid import ObjectId # Used to generate a unique ID for the report

load_dotenv() # Loading environment variables from .env file

db_service = DatabaseService() # Initializing the DatabaseService class

# Get the ZAP image name from environment variables
ZAP_IMAGE = os.getenv('ZAP_IMAGE') # The Docker image for OWASP ZAP

# Setting the reports directory
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports', 'zap_outputs')
ENHANCED_REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports', 'enhanced_reports')

# Ensure the reports directory exists with proper permissions
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(ENHANCED_REPORTS_DIR, exist_ok=True)

# The base shared stuff among all the scans
def run_zap_scan(target_url: AnyHttpUrl, scan_type: ScanType, scan_command: List[str], reports_folder: str, report_name: str, report_type: ReportType, report_format: ReportFormat):
    # Initializing the Docker client
    client = docker.from_env()

    try:
            # Initializing and running the OWASP ZAP container for scanning
            container = client.containers.run(
                ZAP_IMAGE,  # The Docker image name holder variable
                command=scan_command,  # The command to run within the container
                detach=True,  # Runs container in background to avoid blocking
                volumes={
                    reports_folder: {'bind': '/zap/wrk', 'mode': 'rw'}  # Mounting the report directory inside the container
                },
                working_dir='/zap/wrk',  # Setting the working directory inside the container
                remove=True,  # Cleans up container after completion to save resources
                network_mode='host',  # Ensures direct network access for accurate scanning
                user='root'  # Run container as root to ensure write permissions
            )

            # Block until scan completion and collect results
            result = container.wait()  # Waits for container to finish execution
            logs = container.logs().decode('utf-8')  # Retrieves and decodes container logs

            # Determining scan status based on exit code
            scan_status = "Completed" if result["StatusCode"] == 0 else "Failed"

            # Verifying the report generation and setting paths for access
            report_paths = {
                'html': os.path.join(reports_folder, f'{report_name}.html'),
                'xml': os.path.join(reports_folder, f'{report_name}.xml'),
                'json': os.path.join(reports_folder, f'{report_name}.json')
            }
            
            # Verifying if all the reports exist
            for report_type_key, path in report_paths.items():
                if not os.path.exists(path):
                    print(f"Warning: {report_type_key} report not generated at {path}")
            
            # Initializing the AI analysis result
            ai_result = None
            md_report_path = None
            pdf_report_path = None
            
            if report_type == ReportType.ENHANCED and os.path.exists(report_paths['xml']):
                try:
                    # Ensure the outputs directory exists
                    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports", "outputs")
                    os.makedirs(output_dir, exist_ok=True)
                    os.chmod(output_dir, 0o777)  # Ensure proper permissions
                    
                    # Run AI analysis
                    ai_result = analyze_vulnerabilities(report_paths['xml']) #Pssing the XML report path to the AI analysis function
                    if ai_result and ai_result.get("success"):
                        print(f"AI analysis completed successfully for {report_paths['xml']}")
                        
                        # Get the markdown report path
                        base_name = os.path.splitext(os.path.basename(report_paths['xml']))[0] # Extracting the base name of the report
                        md_report_name = f"{base_name}.md"
                        md_report_path = os.path.join(output_dir, md_report_name) 
                        
                        # Ensure the markdown report exists
                        if not os.path.exists(md_report_path):
                            print(f"Warning: Markdown report not generated at {md_report_path}")
                            md_report_path = None
                        else:
                            # Using the visuals_enhancer to create enhanced PDF report
                            try:
                                print("Generating enhanced PDF report...")
                                enhanced_output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports", "enhanced")
                                os.makedirs(enhanced_output_dir, exist_ok=True)
                                
                                # Getting the folder name from the reports_folder path
                                folder_name = os.path.basename(reports_folder)
                                
                                # Creating the same subfolder structure in enhanced directory
                                enhanced_subfolder = os.path.join(enhanced_output_dir, folder_name)
                                os.makedirs(enhanced_subfolder, exist_ok=True)
                                
                                # Calling enhance_report to generate PDF 
                                enhanced_result = enhance_report(
                                    input_md_path=md_report_path,
                                    output_dir=enhanced_subfolder,
                                    preserve_filename=True,
                                    output_format="pdf"  
                                )
                                
                                # Geting the PDF path from the result
                                if enhanced_result and "pdf_path" in enhanced_result:
                                    pdf_report_path = enhanced_result["pdf_path"]
                                    print(f"Enhanced PDF report generated at {pdf_report_path}")
                                    
                                    # Creating a folder in enhanced_reports directory with the same name as in zap_outputs
                                    # Using the same folder name as in reports_folder
                                    target_folder = os.path.join(ENHANCED_REPORTS_DIR, folder_name)
                                    os.makedirs(target_folder, exist_ok=True)
                                    
                                    # Copying the XML and JSON reports to the enhanced_reports folder
                                    for report_format in ['xml', 'json']:
                                        if report_format in report_paths and os.path.exists(report_paths[report_format]):
                                            target_path = os.path.join(target_folder, os.path.basename(report_paths[report_format]))
                                            shutil.copy2(report_paths[report_format], target_path)
                                            print(f"Copied {report_format} report to {target_path}")
                                    
                                    # Copying the PDF report to the enhanced_reports folder
                                    pdf_target_path = os.path.join(target_folder, os.path.basename(pdf_report_path))
                                    shutil.copy2(pdf_report_path, pdf_target_path)
                                    print(f"Copied PDF report to {pdf_target_path}")
                                    
                                    # Updating the report paths to point to the new location
                                    for report_format in ['xml', 'json']:
                                        if report_format in report_paths and os.path.exists(report_paths[report_format]):
                                            report_paths[report_format + '_enhanced'] = os.path.join(target_folder, os.path.basename(report_paths[report_format]))
                                    
                                    # Add enhanced PDF path
                                    report_paths['pdf_enhanced'] = pdf_target_path
                                else:
                                    print("Warning: Enhanced PDF report generation failed")
                            except Exception as e:
                                print(f"Error generating enhanced PDF report: {e}")
                    else:
                        error_msg = ai_result.get("error", "Unknown error") if ai_result else "AI analysis failed"
                        print(f"AI analysis failed: {error_msg}")
                except Exception as e:
                    print(f"Error during AI analysis: {e}")
                    ai_result = {"success": False, "error": str(e)}
                    md_report_path = None

            # Prepare scan output with all relevant information
            scan_output = {
                "status": scan_status,
                "target": target_url,
                "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type), # Using the value of the enum instead of the enum itself, hasattr checks if the enum has a value attribute
                "report_type": report_type.value if hasattr(report_type, 'value') else str(report_type),
                "report_format": report_format.value if hasattr(report_format, 'value') else str(report_format),
                "exit_code": result["StatusCode"],
                "logs": logs,
                "reports": {
                    report_type_key: path if os.path.exists(path) else None
                    for report_type_key, path in report_paths.items()
                },
                "completed": True  # Explicitly mark as completed
            }
            
            # Add markdown report path to the output if available
            if md_report_path and os.path.exists(md_report_path):
                scan_output["reports"]["markdown"] = md_report_path
                
            # Add PDF report path to the output if available
            if pdf_report_path and os.path.exists(pdf_report_path):
                scan_output["reports"]["pdf"] = pdf_report_path

            # Add enhanced reports folder path if it was created
            if report_type == ReportType.ENHANCED and "pdf_enhanced" in report_paths:
                scan_output["enhanced_reports_folder"] = os.path.dirname(report_paths["pdf_enhanced"])
            
            # Add AI analysis results to the output if available
            if ai_result:
                # Only include successful analysis results or include error information
                if isinstance(ai_result, dict):
                    if ai_result.get("success", False):
                        # Include full analysis for successful results
                        scan_output["ai_analysis"] = ai_result
                    else:
                        # Include error information for failed analysis
                        scan_output["ai_analysis"] = {"success": False, "error": ai_result.get("error", "Unknown error")}
                else:
                    # Handle case where ai_result is not a dictionary
                    scan_output["ai_analysis"] = {"success": False, "error": "Invalid analysis result format"}
            else:
                # Ensure ai_analysis is always included in the output
                scan_output["ai_analysis"] = {"success": False, "error": "AI analysis was not performed"}
                
            # Saving the reports to the database 
            try:
                # Saving the report to the database then getting the file IDs
                print("Saving reports to database...")
                report_id = db_service.save_report(
                    scan_id=f"scan_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                    target_url=target_url,
                    report_type=report_type.value if hasattr(report_type, 'value') else str(report_type),
                    report_format=report_format.value if hasattr(report_format, 'value') else str(report_format),
                    report_paths=scan_output["reports"],
                    ai_analysis=ai_result
                )
                
                print(f"Reports saved to database with ID: {report_id}")
                
                # Get the file IDs from the saved report
                saved_report = db_service.get_report(report_id)
                if saved_report and "file_paths" in saved_report:
                    # Extract file IDs
                    gridfs_file_ids = {}
                    for key, value in saved_report["file_paths"].items():
                        if key.endswith("_id"):
                            file_type = key[:-3]  # Remove '_id' suffix
                            gridfs_file_ids[file_type] = value
                    
                    # Add file IDs to output
                    scan_output["gridfs_file_ids"] = gridfs_file_ids
                    scan_output["report_id"] = report_id
                    
                    print(f"Added GridFS file IDs to output: {gridfs_file_ids}")
                else:
                    print("Failed to retrieve saved report or no file paths found")
            except Exception as e:
                print(f"Error saving reports to database: {str(e)}")

            return scan_output

    # Checking for the image
    except docker.errors.ImageNotFound:
        return {
            "status": "Failed",
            "target": target_url,
            "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type),
            "error": "Local OWASP ZAP docker image not found. Please build the image first."
        }
    # Handling other exceptions
    except docker.errors.APIError as e:
        return {
            "status": "Failed",
            "target": target_url,
            "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type),
            "error": f"Docker API error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "Failed",
            "target": target_url,
            "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type),
            "error": str(e)
        }

@celery.task
def run_scan(target_url: AnyHttpUrl, scan_type: ScanType, report_type: ReportType, report_format: ReportFormat):
    try:
        # Converting scan_type to ScanType enum if its a string(It's passed as a string for some reason)
        if isinstance(scan_type, str):
            try:
                scan_type = ScanType(scan_type)
            except ValueError as e:
                return {
                    "status": "Failed",
                    "target": target_url,
                    "scan_type": scan_type,
                    "error": f"Invalid scan type: {scan_type}. Error: {str(e)}"
                }
            
        # Converting report_type and report_format to their respective enums if they are strings
        if isinstance(report_type, str):
            try:
                report_type = ReportType(report_type)
            except ValueError as e:
                return {
                    "status": "Failed",
                    "target": target_url,
                    "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type),
                    "error": f"Invalid report type: {report_type}. Error: {str(e)}"
                }

        # Coverting report_format to ReportFormat enum if its a string to avoid the bug happened in the scan_type case    
        if isinstance(report_format, str):
            try:
                report_format = ReportFormat(report_format)
            except ValueError as e:
                return {
                    "status": "Failed",
                    "target": target_url,
                    "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type),
                    "error": f"Invalid report format: {report_format}. Error: {str(e)}"
                }

        # Generating a unique report name using current timestamp to avoid overwriting
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") # ".strftime" formats the timestamp to a string
        report_name = f"zap_report_{timestamp}"

        # Creating a folder for the reports for better organization
        try:
            reports_folder = os.path.join(REPORT_DIR, f"{scan_type.value}-scan_{timestamp}")
            os.makedirs(reports_folder, exist_ok=True)
            os.chmod(reports_folder, 0o777)   # Setting proper permissions for the reports_folder
        except Exception as e:
            return {
                "status": "Failed",
                "target": target_url,
                "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type),
                "error": f"Failed to create reports directory: {str(e)}"
            }
        
        # Saving the scan results to be able to return them to the frontend
        scan_result = None
        
        # Running basic scan
        if scan_type == ScanType.BASIC: # Using the ScanType enum to access the values instead of hardcoding the strings
            # Initializing the command for the ZAP container(Basic scan)
            scan_command = [
                "zap-baseline.py",
                "-t", target_url,
                "-I",  # Use the internal ZAP daemon
                "-d",  # Used to show debug information
                "-r", f"{report_name}.html",
                "-x", f"{report_name}.xml",
                "-J", f"{report_name}.json"
            ]
            scan_result = run_zap_scan(target_url, scan_type, scan_command, reports_folder, report_name, report_type, report_format)

        elif scan_type == ScanType.FULL:
            # Initializing the command for the ZAP container(Full scan with enhanced capabilities)
            scan_command = [
                "zap-full-scan.py",
                "-t", target_url,
                "-I",  # Internal ZAP daemon
                "-d",  # Debug
                "-j",  # AJAX Spider
                "-m", "5",  # Spider time, 5 minutes for deeper crawling
                "-T", "10",  # Scan time, 10 minutes for more thorough testing
                "-z", "sqli,xss,xxe",  # Enhanced attack mode with SQL, XSS,and XXE testing
                "--hook=zapHooks.py",  # Support for custom hooks if available
                "--script-timeout", "120",  # Increased script timeout for complex scripts
                "--ajax-timeout", "60",  # Increased AJAX timeout for complex applications
                "--scan-delay", "1000",  # Added a delay between requests to avoid overwhelming the target
                "--recursive",  # Enables recursive scanning for deeper analysis
                "-r", f"{report_name}.html",
                "-x", f"{report_name}.xml",
                "-J", f"{report_name}.json"
            ]
            scan_result = run_zap_scan(target_url, scan_type, scan_command, reports_folder, report_name, report_type, report_format)

        elif scan_type == ScanType.API_SCAN:
            # Initializing the command for the ZAP container(API scan)
            scan_command = [
                "zap-api-scan.py",
                "-t", target_url,
                "-I",  # Internal ZAP daemon
                "-d",  # Debug
                "-f", "openapi",  # Telling ZAP that the API format is openapi(Swagger)
                "-r", f"{report_name}.html",
                "-x", f"{report_name}.xml",
                "-J", f"{report_name}.json"
            ]
            scan_result = run_zap_scan(target_url, scan_type, scan_command, reports_folder, report_name, report_type, report_format)

        elif scan_type == ScanType.SPIDER_SCAN:
            # Initializing the command for the ZAP container(Spider scan)
            scan_command = [
                "zap-spider-scan.py",
                "-t", target_url,
                "-I",  # Internal ZAP daemon
                "-d",  # Debug
                "-m", "5",  # Spider time, 5 minutes for deeper crawling
                "-r", f"{report_name}.html",
                "-x", f"{report_name}.xml",
                "-J", f"{report_name}.json" 
            ]
            scan_result = run_zap_scan(target_url, scan_type, scan_command, reports_folder, report_name, report_type, report_format)
        else:
            return {
                "status": "Invalid scan type",
                "target": target_url,
                "scan_type": scan_type.value if hasattr(scan_type, 'value') else str(scan_type)
            }
        
        return scan_result
    except Exception as e:
        return {
            "status": "Failed",
            "target": target_url,
            "scan_type": scan_type.value if hasattr(scan_type, 'value') and 'scan_type' in locals() else "Unknown",
            "error": f"Unexpected error in run_scan: {str(e)}"
        }
