# This file is for handling the Celery tasks.
from ..services.celery_service import celery # Importing the celery instance from celery_service
from pydantic import AnyHttpUrl
from ..models.scan_model import ScanType
import docker
import datetime
import os
from dotenv import load_dotenv # Used to import from the .env file

load_dotenv() # Loading environment variables from .env file

# Get the ZAP image name from environment variables
ZAP_IMAGE = os.getenv('ZAP_IMAGE') # The Docker image for OWASP ZAP

@celery.task
def run_scan(target_url: AnyHttpUrl, scan_type: ScanType):
    client = docker.from_env()

    # Setting the reports directory
    REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports', 'zap_outputs')
    
    # Ensure the reports directory exists with proper permissions
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    # Running basic scan
    if scan_type == "basic":
        try:
            # Generating a unique report name using current timestamp to avoid overwriting
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") # ".strftime" formats the timestamp to a string
            report_name = f"zap_report_{timestamp}"

            # Initalizing the command for the ZAP container(Basic scan)
            basicScan_command = [
                "zap-baseline.py",
                "-t", target_url,
                "-I",  # Use the internal ZAP daemon
                "-d",  # Used to show debug information
                "-r", f"{report_name}.html",
                "-x", f"{report_name}.xml",
                "-J", f"{report_name}.json"
            ]
            
            # Initializing and running the OWASP ZAP container for scanning
            os.chmod(REPORT_DIR, 0o777)   # Setting proper permissions for the reports directory

            container = client.containers.run(
                ZAP_IMAGE,  # The Docker image name holder variable
                command=basicScan_command,  # The command to run within the container(I defined it earlier)
                detach=True,  # Runs container in background to avoid blocking
                volumes={
                    REPORT_DIR: {'bind': '/zap/wrk', 'mode': 'rw'}  # Mounting the report directory inside the container
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
            html_report_path = os.path.join(REPORT_DIR, f"{report_name}.html") # Path to the HTML report
            xml_report_path = os.path.join(REPORT_DIR, f"{report_name}.xml") # Path to the XML report
            json_report_path = os.path.join(REPORT_DIR, f"{report_name}.json") # Path to the JSON report
            
            scan_output = {
                "status": scan_status,
                "target": target_url,
                "scan_type": scan_type,
                "exit_code": result["StatusCode"],
                "logs": logs,
                "reports": {
                    "html": html_report_path if os.path.exists(html_report_path) else None,
                    "xml": xml_report_path if os.path.exists(xml_report_path) else None,
                    "json": json_report_path if os.path.exists(json_report_path) else None
                }
            }

            return scan_output

        # Checking for the image
        except docker.errors.ImageNotFound:
            return {
                "status": "Failed",
                "target": target_url,
                "scan_type": scan_type,
                "error": "Local OWASP ZAP docker image not found. Please build the image first."
            }

        except Exception as e:
            return {
                "status": "Failed",
                "target": target_url,
                "scan_type": scan_type,
                "error": str(e)
            }
    # Handling invalid scan types
    return {
        "status": "Invalid scan type",
        "target": target_url,
        "scan_type": scan_type
    }
