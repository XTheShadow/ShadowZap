# This file is for handling the Celery tasks.
from ..services.celery_service import celery # Importing the celery instance from celery_service
from pydantic import AnyHttpUrl
from ..models.scan_model import ScanType
from typing import List # A pyton library that introduces a new data type called List
import docker
import datetime
import os
from dotenv import load_dotenv # Used to import from the .env file

load_dotenv() # Loading environment variables from .env file

# Get the ZAP image name from environment variables
ZAP_IMAGE = os.getenv('ZAP_IMAGE') # The Docker image for OWASP ZAP

# Setting the reports directory
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports', 'zap_outputs')

# Ensure the reports directory exists with proper permissions
os.makedirs(REPORT_DIR, exist_ok=True)

# The base shared stuff among all the scans
def run_zap_scan(target_url: AnyHttpUrl, scan_type: ScanType, scan_command: List[str], reports_folder: str, report_name: str):
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
            for report_type, path in report_paths.items():
                if not os.path.exists(path):
                    print(f"Warning: {report_type} report not generated at {path}")
            
            scan_output = {
                "status": scan_status,
                "target": target_url,
                "scan_type": scan_type,
                "exit_code": result["StatusCode"],
                "logs": logs,
                "reports": {
                    report_type: path if os.path.exists(path) else None
                    for report_type, path in report_paths.items()
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

@celery.task
def run_scan(target_url: AnyHttpUrl, scan_type: ScanType):
    # Generating a unique report name using current timestamp to avoid overwriting
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") # ".strftime" formats the timestamp to a string
    report_name = f"zap_report_{timestamp}"

    # Creating a folder for the reports for better organization
    reports_folder = os.path.join(REPORT_DIR, f"{scan_type}-scan_{timestamp}")
    os.makedirs(reports_folder, exist_ok=True)
    os.chmod(reports_folder, 0o777)   # Setting proper permissions for the reports_folder

    # Running basic scan
    if scan_type == "basic":
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
        return run_zap_scan(target_url, scan_type, scan_command, reports_folder, report_name)

    # Handling invalid scan types
    return {
        "status": "Invalid scan type",
        "target": target_url,
        "scan_type": scan_type
    }
