from fastapi import FastAPI, HTTPException, Response, Path, Query, Body, Request
import uvicorn
from fastapi.middleware.cors import CORSMiddleware # Importing the CORSMiddleware class
from fastapi.responses import FileResponse, JSONResponse # Importing the FileResponse and JSONResponse classes
from ..tasks.scan_tasks import run_scan # Importing the run_scan function from the scan_tasks.py file
from ..models.scan_model import ScanRequest, ScanType, ReportType, ReportFormat # Importing the ScanRequest class from the scan_model.py file
from ..services.database_service import DatabaseService # Importing the DatabaseService class from the database_service.py file
from celery.result import AsyncResult # Importing the AsyncResult class from the celery.result module to check the status of the task
import os # Importing the os module to handle file operations
from typing import List, Optional, Dict, Any
import tempfile # Importing the tempfile module to create a temporary file
from bson.objectid import ObjectId # Importing the ObjectId class from the bson module to convert string IDs to MongoDB ObjectId
import logging # Importing the logging module to log messages to the console
from fastapi.responses import RedirectResponse # This is used to redirect the user to the file endpoint
from fastapi.background import BackgroundTasks # This is used to add a background task to the response
import datetime 
import uuid # Importing the uuid module to generate unique IDs

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the application
app = FastAPI(title="ShadowZAP API", description="API for the ShadowZAP automated penetration testing tool")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods just to make sure I dont get an error due to CORS
    allow_headers=["*"],
)

# Initialize database service
db_service = DatabaseService()

# Root endpoint
@app.get("/")
def root():
    return {"status": "ok", "message": "ShadowZap API is running"}

# Endpoint to start a new scan
@app.post("/scan")
# Async functions are used for coroutines so it can be suspended and resumed
async def start_Scan(scan_request: ScanRequest, request: Request): # An object "scan_request" from the "ScanRequest" class was created
    logger.info(f"Scan request received: target_url={scan_request.target_url}, scan_type={scan_request.scan_type}, report_type={scan_request.report_type}, report_format={scan_request.report_format}")
    
    # Get or create a web session ID from cookies or headers
    web_session_id = request.cookies.get("session_id")
    if not web_session_id:
        # If no session ID in cookies, check headers
        web_session_id = request.headers.get("X-Session-ID")
        
    # If still no session ID, generate a new one
    if not web_session_id:
        web_session_id = f"web_session_{uuid.uuid4()}"
        logger.info(f"Generated new web session ID: {web_session_id}")
    else:
        logger.info(f"Using existing web session ID: {web_session_id}")
    
    # Start the scan task
    task = run_scan.delay(
        str(scan_request.target_url), # Here the target_url is converted to a string for celery
        scan_request.scan_type.value,  # This is to get the scan type value from the ScanType class(Enum)
        scan_request.report_type.value,  # This is to get the report type value from the ReportType class(Enum)
        scan_request.report_format.value  # To get the report format value from the ReportFormat class(Enum)
    )
    
    # Store the web session ID in the database for this task
    try:
        db_service.scans.update_one(
            {"task_id": str(task.id)},
            {"$set": {"web_session_id": web_session_id}},
            upsert=True
        )
        logger.info(f"Associated web session ID {web_session_id} with task {task.id}")
    except Exception as e:
        logger.error(f"Error storing web session ID: {str(e)}")
    
    # Prepare the response
    response_data = {
        "status": "Scan initiated",
        "task_id": str(task.id),
        "target_url": scan_request.target_url,
        "scan_type": scan_request.scan_type.value,
        "web_session_id": web_session_id
    }
    
    # Create response with cookie
    response = JSONResponse(content=response_data)
    response.set_cookie(
        key="session_id",
        value=web_session_id,
        max_age=60*60*24*30,  # 30 days
        httponly=True,
        samesite="lax" # This is used to prevent CSRF attacks by ensuring that the cookie is only sent to the same site
    )
    
    return response

# Endpoint to check scan status
@app.get("/scan/{task_id}")
async def get_scan_status(task_id: str):
    # Check Celery task status
    task_result = AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        response = {
            "status": "Pending",
            "task_id": task_id
        }
    elif task_result.state == 'FAILURE':
        response = {
            "status": "Failed",
            "task_id": task_id,
            "error": str(task_result.result)
        }
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        response = {
            "status": result.get("status", "Completed"),
            "task_id": task_id,
            "report_type": result.get("report_type", "")
        }
        
        # Include scan_id if available
        if "scan_id" in result:
            response["scan_id"] = result["scan_id"]
        
        # Include reports and other result data
        if "reports" in result:
            response["reports"] = result["reports"]
            
        # Include GridFS file IDs if available
        if "gridfs_file_ids" in result:
            response["gridfs_file_ids"] = result["gridfs_file_ids"]
            
        # Include report_id if available
        if "report_id" in result:
            response["report_id"] = result["report_id"]
        else:
            # Try to find the latest report for this task
            logger.info(f"Looking for reports for task {task_id}")
            try:
                # Check if there are any reports in the database
                reports = list(db_service.reports.find().sort("timestamp", -1).limit(1))
                if reports:
                    latest_report = reports[0]
                    logger.info(f"Found report: {latest_report['report_id']}")
                    
                    # Extract file IDs from the report
                    file_ids = {}
                    for key, value in latest_report.get("file_paths", {}).items():
                        if key.endswith("_id"):
                            file_type = key[:-3]  # Remove '_id' suffix
                            file_ids[file_type] = value
                    
                    if file_ids:
                        logger.info(f"Found file IDs: {file_ids}")
                        response["gridfs_file_ids"] = file_ids
                        response["report_id"] = latest_report["report_id"]
                else:
                    logger.info("No reports found in database")
            except Exception as e:
                logger.error(f"Error finding reports: {str(e)}")
        
        # Try to get web_session_id from the database
        try:
            scan_record = db_service.scans.find_one({"task_id": task_id})
            if scan_record and "web_session_id" in scan_record:
                response["web_session_id"] = scan_record["web_session_id"]
                logger.info(f"Found web_session_id for task {task_id}: {scan_record['web_session_id']}")
        except Exception as e:
            logger.error(f"Error retrieving web_session_id: {str(e)}")
            
        # Ensure the frontend knows the scan is completed
        if response["status"] == "Completed":
            response["completed"] = True
    else:
        response = {
            "status": "Running",
            "task_id": task_id
        }
    
    logger.info(f"Scan status response: {response}")
    return response

# Endpoint to get a report file by its GridFS ID
@app.get("/files/{file_id}")
async def get_file_by_id(file_id: str, background_tasks: BackgroundTasks):
    try:
        logger.info(f"Retrieving file with ID: {file_id}")
        # Check if file exists in GridFS
        try:
            object_id = ObjectId(file_id)
            if not db_service.fs.exists(object_id):
                logger.error(f"File with ID {file_id} not found")
                raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
            
            # Get file from GridFS
            grid_file = db_service.fs.get(object_id)
        except Exception as e:
            logger.error(f"Error retrieving file from GridFS: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving file from GridFS: {str(e)}")
            
        logger.info(f"Retrieved file: {grid_file.filename}, content_type: {grid_file.content_type}")
        
        # Create a temporary file to serve
        suffix = os.path.splitext(grid_file.filename)[1] if grid_file.filename else ""
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                # Read the file content as bytes
                content = grid_file.read()
                
                # Checking if content is a function (which can happen with certain GridFS implementations)
                if callable(content):
                    logger.warning("File content is a function, attempting to call it")
                    content = content()
                
                # Ensuring that the content is bytes
                if not isinstance(content, bytes):
                    logger.warning(f"Content is not bytes, it's {type(content)}. Converting to bytes.")
                    content = str(content).encode('utf-8')
                
                temp_file.write(content)
                temp_path = temp_file.name
                
            # Get content type
            content_type = grid_file.content_type or "application/octet-stream"
            logger.info(f"Serving file from temporary path: {temp_path}")
            
            # Adding a cleanup task to delete the temporary file after response is sent
            background_tasks.add_task(lambda: os.unlink(temp_path) if os.path.exists(temp_path) else None)
            
            return FileResponse(
                path=temp_path,
                filename=grid_file.filename or f"file_{file_id}{suffix}",
                media_type=content_type
            )
        except Exception as e:
            logger.error(f"Error creating temporary file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating temporary file: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")

# Alternative endpoint to download files directly from filesystem
@app.get("/direct-files/{report_id}/{file_type}")
async def get_file_direct(report_id: str, file_type: str):
    try:
        logger.info(f"Retrieving file directly for report {report_id}, file type {file_type}")
        # Find the report
        report = db_service.get_report(report_id)
        if not report:
            logger.error(f"Report with ID {report_id} not found")
            raise HTTPException(status_code=404, detail=f"Report with ID {report_id} not found")
        
        # Check if the file path exists
        file_path_key = file_type
        if file_path_key not in report.get("file_paths", {}):
            logger.error(f"File type {file_type} not found in report {report_id}")
            raise HTTPException(status_code=404, detail=f"File type {file_type} not found in report {report_id}")
        
        file_path = report["file_paths"][file_path_key]
        
        # Get project root directory for resolving relative paths
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # If the path is relative (doesn't start with a drive letter or slash), make it absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(project_root, file_path)
            logger.info(f"Converted relative path to absolute: {file_path}")
        
        # Check if the file exists at the specified path
        if not os.path.exists(file_path):
            # Check if we have a GridFS ID for this file type
            gridfs_key = f"{file_type}_id"
            if gridfs_key in report.get("file_paths", {}):
                file_id = report["file_paths"][gridfs_key]
                logger.info(f"File not found on filesystem, using GridFS ID {file_id}")
                return RedirectResponse(url=f"/files/{file_id}")
            
            # If still not found, raise 404
            logger.error(f"File {file_path} not found")
            raise HTTPException(status_code=404, detail=f"File {file_path} not found")
        
        # Determine content type
        content_type = "application/octet-stream"
        if file_type.endswith("html"):
            content_type = "text/html"
        elif file_type.endswith("pdf"):
            content_type = "application/pdf"
        elif file_type.endswith("json"):
            content_type = "application/json"
        elif file_type.endswith("xml"):
            content_type = "application/xml"
        elif file_type.endswith("md") or file_type.endswith("markdown"):
            content_type = "text/markdown"
            
        logger.info(f"Serving file directly from: {file_path}")
        
        # For HTML files, set content_disposition_type to "inline" to render in browser
        if content_type == "text/html":
            return FileResponse(
                path=file_path,
                filename=os.path.basename(file_path),
                media_type=content_type,
                content_disposition_type="inline"
            )
        else:
            return FileResponse(
                path=file_path,
                filename=os.path.basename(file_path),
                media_type=content_type
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file directly: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving file directly: {str(e)}")

# Endpoint to serve enhanced HTML reports directly by their report ID
@app.get("/enhanced-html/{report_id}")
async def get_enhanced_html(report_id: str):
    try:
        logger.info(f"Retrieving enhanced HTML report for report {report_id}")
        
        # Find the report
        report = db_service.get_report(report_id)
        if not report:
            logger.error(f"Report with ID {report_id} not found")
            raise HTTPException(status_code=404, detail=f"Report with ID {report_id} not found")
        
        # Get project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Get the scan ID from the report
        scan_id = report.get("scan_id", "")
        if not scan_id:
            logger.error(f"Scan ID not found in report {report_id}")
            raise HTTPException(status_code=404, detail=f"Scan ID not found in report {report_id}")
        
        # Check for web HTML file path in the report
        web_html_path = report.get("file_paths", {}).get("web_html_path", "")
        if web_html_path:
            # If the path is relative, make it absolute
            if not os.path.isabs(web_html_path):
                web_html_path = os.path.join(project_root, web_html_path)
            
            # Check if the file exists
            if os.path.exists(web_html_path):
                logger.info(f"Found web HTML report at {web_html_path}")
                return FileResponse(
                    path=web_html_path,
                    filename=os.path.basename(web_html_path),
                    media_type="text/html",
                    content_disposition_type="inline"
                )
        
        # If we still don't have a file, look in the standard output folder
        output_dir = os.path.join(project_root, "reports", "outputs")
        if os.path.exists(output_dir):
            web_html_files = [f for f in os.listdir(output_dir) if f.endswith("_web.html")]
            if web_html_files:
                # Sort by modification time to get the most recent
                web_html_files.sort(key=lambda f: os.path.getmtime(os.path.join(output_dir, f)), reverse=True)
                web_html_path = os.path.join(output_dir, web_html_files[0])
                logger.info(f"Found web HTML report at {web_html_path}")
                return FileResponse(
                    path=web_html_path,
                    filename=os.path.basename(web_html_path),
                    media_type="text/html",
                    content_disposition_type="inline"
                )
        
        logger.error(f"Enhanced web HTML report not found for report {report_id}")
        raise HTTPException(status_code=404, detail=f"Enhanced web HTML report not found for report {report_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving enhanced HTML report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving enhanced HTML report: {str(e)}")

# Endpoint to serve enhanced HTML report by session ID
@app.get("/session-reports/{session_id}/enhanced-html")
async def get_session_enhanced_html(session_id: str):
    try:
        logger.info(f"Retrieving enhanced HTML report for session {session_id}")
        
        # Get project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Find the most recent report associated with this session
        try:
            reports = list(db_service.reports.find(
                {"web_session_id": session_id}
            ).sort("timestamp", -1).limit(1))
            
            if reports:
                latest_report = reports[0]
                logger.info(f"Found latest report for session {session_id}: {latest_report['report_id']}")
                
                # Check for web HTML file path in the report
                web_html_path = latest_report.get("file_paths", {}).get("web_html_path", "")
                if web_html_path:
                    # If the path is relative, make it absolute
                    if not os.path.isabs(web_html_path):
                        web_html_path = os.path.join(project_root, web_html_path)
                    
                    # Check if the file exists
                    if os.path.exists(web_html_path):
                        logger.info(f"Found web HTML report at {web_html_path}")
                        return FileResponse(
                            path=web_html_path,
                            filename=os.path.basename(web_html_path),
                            media_type="text/html",
                            content_disposition_type="inline"
                        )
                
                # If we have a scan ID, try to find the report in the outputs folder
                scan_id = latest_report.get("scan_id", "")
                if scan_id:
                    output_dir = os.path.join(project_root, "reports", "outputs")
                    if os.path.exists(output_dir):
                        web_html_files = [f for f in os.listdir(output_dir) if f.endswith("_web.html")]
                        if web_html_files:
                            # Sort by modification time to get the most recent
                            web_html_files.sort(key=lambda f: os.path.getmtime(os.path.join(output_dir, f)), reverse=True)
                            web_html_path = os.path.join(output_dir, web_html_files[0])
                            logger.info(f"Found web HTML report at {web_html_path}")
                            return FileResponse(
                                path=web_html_path,
                                filename=os.path.basename(web_html_path),
                                media_type="text/html",
                                content_disposition_type="inline"
                            )
        except Exception as e:
            logger.warning(f"Error finding reports for session {session_id}: {str(e)}")
        
        # Checking  in the standard outputs folder as a fallback
        outputs_folder = os.path.join(project_root, "reports", "outputs")
        if os.path.exists(outputs_folder):
            web_html_files = [f for f in os.listdir(outputs_folder) if f.endswith("_web.html")]
            if web_html_files:
                # Use the most recent file
                web_html_files.sort(key=lambda f: os.path.getmtime(os.path.join(outputs_folder, f)), reverse=True)
                web_html_path = os.path.join(outputs_folder, web_html_files[0])
                logger.info(f"Found web HTML report in outputs folder: {web_html_path}")
                return FileResponse(
                    path=web_html_path,
                    filename=os.path.basename(web_html_path),
                    media_type="text/html",
                    content_disposition_type="inline"
                )
                
        # Checking in the enhanced directory for the web HTML report
        enhanced_dir = os.path.join(project_root, "reports", "enhanced")
        if os.path.exists(enhanced_dir):
            # Look in all subdirectories for web HTML files
            for root, dirs, files in os.walk(enhanced_dir):
                web_html_files = [f for f in files if f.endswith("_web.html")]
                if web_html_files:
                    # Sort by modification time to get the most recent
                    web_html_files.sort(key=lambda f: os.path.getmtime(os.path.join(root, f)), reverse=True)
                    web_html_path = os.path.join(root, web_html_files[0])
                    logger.info(f"Found web HTML report in enhanced directory: {web_html_path}")
                    return FileResponse(
                        path=web_html_path,
                        filename=os.path.basename(web_html_path),
                        media_type="text/html",
                        content_disposition_type="inline"
                    )
                    
        # Check in the enhanced_reports directory
        enhanced_reports_dir = os.path.join(project_root, "reports", "enhanced_reports")
        if os.path.exists(enhanced_reports_dir):
            # Look in all subdirectories for web HTML files
            for root, dirs, files in os.walk(enhanced_reports_dir):
                web_html_files = [f for f in files if f.endswith("_web.html")]
                if web_html_files:
                    # Sort by modification time to get the most recent
                    web_html_files.sort(key=lambda f: os.path.getmtime(os.path.join(root, f)), reverse=True)
                    web_html_path = os.path.join(root, web_html_files[0])
                    logger.info(f"Found web HTML report in enhanced_reports directory: {web_html_path}")
                    return FileResponse(
                        path=web_html_path,
                        filename=os.path.basename(web_html_path),
                        media_type="text/html",
                        content_disposition_type="inline"
                    )
        
        logger.error(f"Enhanced web HTML report not found for session {session_id}")
        raise HTTPException(status_code=404, detail=f"Enhanced web HTML report not found for session {session_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving enhanced HTML report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving enhanced HTML report: {str(e)}")

# Endpoint to serve enhanced PDF report by session ID
@app.get("/session-reports/{session_id}/enhanced-pdf")
async def get_session_enhanced_pdf(session_id: str):
    try:
        logger.info(f"Retrieving enhanced PDF report for session {session_id}")
        
        # Get project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # trying to find the most recent report associated with this session
        try:
            reports = list(db_service.reports.find(
                {"web_session_id": session_id}
            ).sort("timestamp", -1).limit(1))
            
            if reports:
                latest_report = reports[0]
                logger.info(f"Found latest report for session {session_id}: {latest_report['report_id']}")
                
                # Checking for PDF file path in the report
                pdf_path = latest_report.get("file_paths", {}).get("pdf_enhanced", "")
                if pdf_path:
                    # If the path is relative, make it absolute
                    if not os.path.isabs(pdf_path):
                        pdf_path = os.path.join(project_root, pdf_path)
                    
                    # Checking if the file exists
                    if os.path.exists(pdf_path):
                        logger.info(f"Found enhanced PDF report at {pdf_path}")
                        return FileResponse(
                            path=pdf_path,
                            filename=os.path.basename(pdf_path),
                            media_type="application/pdf",
                            content_disposition_type="inline"
                        )
                
                # If we have a scan ID, try to find the PDF in the final directory
                scan_id = latest_report.get("scan_id", "")
                if scan_id:
                    # Checking in final directory first (this is where visuals_enhancer now saves files)
                    final_dir = os.path.join(project_root, "reports", "final")
                    if os.path.exists(final_dir):
                        pdf_files = [f for f in os.listdir(final_dir) if f.endswith(".pdf")]
                        if pdf_files:
                            # Sort by modification time to get the most recent
                            pdf_files.sort(key=lambda f: os.path.getmtime(os.path.join(final_dir, f)), reverse=True)
                            pdf_path = os.path.join(final_dir, pdf_files[0])
                            logger.info(f"Found enhanced PDF report at {pdf_path}")
                            return FileResponse(
                                path=pdf_path,
                                filename=os.path.basename(pdf_path),
                                media_type="application/pdf",
                                content_disposition_type="inline"
                            )
        except Exception as e:
            logger.warning(f"Error finding reports for session {session_id}: {str(e)}")
        
        # Checking in the "final" directory first as a fallback
        final_dir = os.path.join(project_root, "reports", "final")
        if os.path.exists(final_dir):
            pdf_files = [f for f in os.listdir(final_dir) if f.endswith(".pdf")]
            if pdf_files:
                # Sort by modification time to get the most recent
                pdf_files.sort(key=lambda f: os.path.getmtime(os.path.join(final_dir, f)), reverse=True)
                pdf_path = os.path.join(final_dir, pdf_files[0])
                logger.info(f"Found PDF report in final directory: {pdf_path}")
                return FileResponse(
                    path=pdf_path,
                    filename=os.path.basename(pdf_path),
                    media_type="application/pdf",
                    content_disposition_type="inline"
                )
        
        # Checking in the enhanced_reports directory as a fallback
        enhanced_reports_dir = os.path.join(project_root, "reports", "enhanced_reports")
        if os.path.exists(enhanced_reports_dir):
            # Looking in all the subdirectories for PDF files
            for root, dirs, files in os.walk(enhanced_reports_dir):
                pdf_files = [f for f in files if f.endswith(".pdf")]
                if pdf_files:
                    # Sorting by modification time to get the most recent
                    pdf_files.sort(key=lambda f: os.path.getmtime(os.path.join(root, f)), reverse=True)
                    pdf_path = os.path.join(root, pdf_files[0])
                    logger.info(f"Found enhanced PDF report in enhanced_reports directory: {pdf_path}")
                    return FileResponse(
                        path=pdf_path,
                        filename=os.path.basename(pdf_path),
                        media_type="application/pdf",
                        content_disposition_type="inline"
                    )
        
        logger.error(f"Enhanced PDF report not found for session {session_id}")
        raise HTTPException(status_code=404, detail=f"Enhanced PDF report not found for session {session_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving enhanced PDF report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving enhanced PDF report: {str(e)}")

# Endpoint to list files by session ID
@app.get("/sessions/{session_id}/files")
async def list_files_by_session(session_id: str, grouped: bool = Query(True)):
    try:
        logger.info(f"Looking for files with web session ID: {session_id}")
        
        # Finding files in GridFS with the web_session_id metadata
        files = []
        try:
            # Looking for files with web_session_id metadata
            for grid_out in db_service.fs.find({"metadata.web_session_id": session_id}):
                files.append({
                    "file_id": str(grid_out._id),
                    "filename": grid_out.filename,
                    "content_type": grid_out.content_type,
                    "target_url": grid_out.metadata.get("target_url", ""),
                    "scan_type": grid_out.metadata.get("scan_type", ""),
                    "report_type": grid_out.metadata.get("report_type", ""),
                    "report_group": grid_out.metadata.get("report_group", ""),
                    "upload_date": grid_out.upload_date
                })
        except Exception as e:
            logger.warning(f"Error finding files by metadata.web_session_id: {str(e)}")
        
        # If no files found, try to find reports with this web_session_id
        if not files:
            logger.info(f"No files found with metadata.web_session_id, looking for reports with web_session_id")
            reports = list(db_service.reports.find({"web_session_id": session_id}))
            
            for report in reports:
                # Get report group from the report document
                report_group = report.get("report_group", "")
                
                # Get file IDs from report
                for file_type, file_id in report.get("file_paths", {}).items():
                    if file_type.endswith("_id"):
                        try:
                            grid_out = db_service.fs.get(ObjectId(file_id))
                            files.append({
                                "file_id": file_id,
                                "filename": grid_out.filename,
                                "content_type": grid_out.content_type,
                                "target_url": report.get("target_url", ""),
                                "scan_type": report.get("scan_type", ""),
                                "report_type": report.get("report_type", ""),
                                "report_group": report_group,
                                "upload_date": grid_out.upload_date
                            })
                        except Exception as e:
                            logger.warning(f"Error retrieving GridFS file {file_id}: {str(e)}")
        
        if not files:
            logger.warning(f"No files found for web session {session_id}")
            return []  # Return empty list instead of raising an error
        
        # If grouped parameter is False, return flat list of files
        if not grouped:
            logger.info(f"Returning flat list of {len(files)} files for session {session_id}")
            return files
            
        # Group files by report_group if available, otherwise by date
        grouped_files = {}
        for file in files:
            group_key = file.get("report_group", "")
            if not group_key:
                # If no report_group, use date as fallback
                upload_date = file.get("upload_date")
                if upload_date:
                    group_key = upload_date.strftime("%Y%m%d%H%M")
                else:
                    group_key = "unknown"
            
            if group_key not in grouped_files:
                grouped_files[group_key] = {
                    "group_id": group_key,
                    "timestamp": file.get("upload_date"),
                    "target_url": file.get("target_url", ""),
                    "files": []
                }
            
            grouped_files[group_key]["files"].append(file)
        
        # Sort groups by timestamp (newest first)
        sorted_groups = sorted(
            grouped_files.values(), 
            key=lambda x: x["timestamp"] if x["timestamp"] else datetime.min, 
            reverse=True
        )
        
        logger.info(f"Found {len(files)} files in {len(sorted_groups)} groups for web session {session_id}")
        return sorted_groups
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

# Endpoint to list all sessions
@app.get("/sessions")
async def list_sessions(limit: int = Query(10, ge=1, le=100), skip: int = Query(0, ge=0)):
    try:
        logger.info(f"Listing sessions with limit={limit}, skip={skip}")
        sessions = []
        
        # Trying to get sessions from reports collection by web_session_id
        try:
            # Get reports with web_session_id
            reports = list(db_service.reports.find({"web_session_id": {"$exists": True}})
                           .sort("timestamp", -1).skip(skip).limit(limit))
            
            for report in reports:
                # Get the web session ID
                web_session_id = report.get("web_session_id")
                
                if web_session_id:
                    # Count files in this report
                    file_count = sum(1 for key in report.get("file_paths", {}) if key.endswith("_id"))
                    
                    # Trying to find scan status
                    scan_status = None
                    scan_id = report.get("scan_id")
                    if scan_id:
                        # Trying to get scan status from scans collection
                        scan = db_service.scans.find_one({"scan_id": scan_id})
                        if scan:
                            scan_status = scan.get("status")
                    
                    # Checking if this session is already in our list
                    existing_session = next((s for s in sessions if s["session_id"] == web_session_id), None)
                    
                    if existing_session:
                        # Update existing session with more recent data if needed
                        if report.get("timestamp", "") > existing_session.get("timestamp", ""):
                            existing_session.update({
                                "target_url": report.get("target_url", ""),
                                "scan_type": report.get("scan_type", ""),
                                "report_type": report.get("report_type", ""),
                                "timestamp": report.get("timestamp", ""),
                                "status": scan_status or existing_session.get("status")
                            })
                        # Add to file count
                        existing_session["file_count"] += file_count
                    else:
                        # Add new session
                        sessions.append({
                            "session_id": web_session_id,
                            "target_url": report.get("target_url", ""),
                            "scan_type": report.get("scan_type", ""),
                            "report_type": report.get("report_type", ""),
                            "timestamp": report.get("timestamp", ""),
                            "file_count": file_count,
                            "status": scan_status
                        })
        except Exception as e:
            logger.warning(f"Error getting sessions from reports by web_session_id: {str(e)}")
        
        # If no sessions found in reports, try to find sessions in the sessions collection
        if not sessions:
            logger.info("No sessions found in reports, checking sessions collection")
            try:
                # Get sessions from sessions collection
                db_sessions = list(db_service.sessions.find().sort("last_activity", -1).skip(skip).limit(limit))
                
                for session in db_sessions:
                    web_session_id = session.get("web_session_id")
                    if web_session_id:
                        # Try to find scan status
                        scan_status = None
                        scan_ids = session.get("scans", [])
                        if scan_ids and len(scan_ids) > 0:
                            # Get the most recent scan
                            latest_scan = db_service.scans.find_one({"scan_id": {"$in": scan_ids}}, sort=[("timestamp", -1)])
                            if latest_scan:
                                scan_status = latest_scan.get("status")
                                
                        # Add session to list
                        sessions.append({
                            "session_id": web_session_id,
                            "target_url": session.get("target_url", ""),
                            "scan_type": session.get("scan_type", ""),
                            "timestamp": session.get("last_activity", ""),
                            "file_count": session.get("scan_count", 0),
                            "status": scan_status
                        })
            except Exception as e:
                logger.warning(f"Error getting sessions from sessions collection: {str(e)}")
        
        logger.info(f"Found {len(sessions)} sessions")
        return sessions
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")

# Endpoint for dashboard statistics
@app.get("/dashboard")
async def get_dashboard_stats():
    try:
        logger.info("Getting dashboard statistics")
        stats = {
            "totalScans": 0,
            "completedScans": 0,
            "failedScans": 0,
            "enhancedReports": 0,
            "vulnerabilitiesByType": {
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            },
            "recentTargets": [],
            "activeSessions": 0,
            "recentSessions": []
        }
        
        # Try to count scans
        try:
            # Total scans
            stats["totalScans"] = db_service.scans.count_documents({})
            
            # Completed scans - check for both "Completed" and "completed" status values
            completed_query = {
                "$or": [
                    {"status": "Completed"},
                    {"status": "completed"},
                    {"status": "Success"},
                    {"status": "success"}
                ]
            }
            stats["completedScans"] = db_service.scans.count_documents(completed_query)
            
            # Failed scans - check for both "Failed" and "failed" status values
            failed_query = {
                "$or": [
                    {"status": "Failed"},
                    {"status": "failed"},
                    {"status": "Error"},
                    {"status": "error"}
                ]
            }
            stats["failedScans"] = db_service.scans.count_documents(failed_query)
            
            # Enhanced reports - check for both "enhanced" and "ENHANCED" report types
            enhanced_query = {
                "$or": [
                    {"report_type": "enhanced"},
                    {"report_type": "ENHANCED"}
                ]
            }
            stats["enhancedReports"] = db_service.reports.count_documents(enhanced_query)
            
            # Get vulnerability counts
            vulnerability_stats = db_service.scans.aggregate([
                {"$group": {
                    "_id": None,
                    "high": {"$sum": "$vulnerability_count.high"},
                    "medium": {"$sum": "$vulnerability_count.medium"},
                    "low": {"$sum": "$vulnerability_count.low"},
                    "info": {"$sum": "$vulnerability_count.info"}
                }}
            ])
            
            vuln_stats = list(vulnerability_stats)
            
            if vuln_stats:
                stats["vulnerabilitiesByType"] = {
                    "high": vuln_stats[0].get("high", 0),
                    "medium": vuln_stats[0].get("medium", 0),
                    "low": vuln_stats[0].get("low", 0),
                    "info": vuln_stats[0].get("info", 0)
                }
            
            # Get recent targets
            recent_targets = db_service.scans.find().sort("timestamp", -1).limit(5)
            targets = [scan.get("target_url", "") for scan in recent_targets]
            
            # Filter out empty targets and make the list unique
            stats["recentTargets"] = list(dict.fromkeys(filter(None, targets)))
            
            # Get active web sessions (sessions with activity in the last 24 hours)
            one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            
            # Count reports with web_session_id from the last 24 hours
            active_sessions_query = [
                {"$match": {
                    "web_session_id": {"$exists": True},
                    "timestamp": {"$gte": one_day_ago}
                }},
                {"$group": {"_id": "$web_session_id"}},
                {"$count": "count"}
            ]
            
            active_sessions = db_service.reports.aggregate(active_sessions_query)
            active_sessions_list = list(active_sessions)
            
            if active_sessions_list:
                stats["activeSessions"] = active_sessions_list[0].get("count", 0)
            
            # Get recent web sessions
            recent_sessions_query = [
                {"$match": {"web_session_id": {"$exists": True}}},
                {"$sort": {"timestamp": -1}},
                {"$group": {
                    "_id": "$web_session_id",
                    "timestamp": {"$first": "$timestamp"},
                    "target_url": {"$first": "$target_url"}
                }},
                {"$limit": 5}
            ]
            
            recent_sessions = db_service.reports.aggregate(recent_sessions_query)
            recent_sessions_list = list(recent_sessions)
            
            stats["recentSessions"] = [
                {
                    "session_id": session["_id"],
                    "timestamp": session["timestamp"],
                    "target_url": session["target_url"]
                }
                for session in recent_sessions_list if session.get("target_url")
            ]
        except Exception as e:
            logger.warning(f"Error getting some dashboard statistics: {str(e)}")
        
        logger.info("Dashboard statistics retrieved")
        return stats
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting dashboard statistics: {str(e)}")

# Endpoint to get scan by session ID
@app.get("/scan-by-session/{session_id}")
async def get_scan_by_session(session_id: str):
    try:
        logger.info(f"Looking for scan with web session ID: {session_id}")
        
        # Find scan with this web_session_id
        scan = db_service.scans.find_one({"web_session_id": session_id})
        
        if not scan:
            logger.warning(f"No scan found with web_session_id {session_id}")
            raise HTTPException(status_code=404, detail=f"No scan found with web_session_id {session_id}")
        
        # Convert ObjectId to string for JSON serialization
        if "_id" in scan:
            scan["_id"] = str(scan["_id"])
            
        logger.info(f"Found scan for session {session_id}: {scan.get('scan_id')}, task_id: {scan.get('task_id')}")
        return scan
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving scan by session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving scan by session: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)