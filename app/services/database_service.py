# This file is for handling database operations with MongoDB.
from pymongo import MongoClient
import os
from datetime import datetime
import gridfs                # Used for storing large files in MongoDB
from bson.objectid import ObjectId # Used to convert string IDs to MongoDB ObjectId
from dotenv import load_dotenv


load_dotenv()

class DatabaseService:
    """Service for interacting with MongoDB database for the ShadowZAP application"""
    
    def __init__(self):
        # Getting the MongoDB connection details from the environment variables
        mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
        mongodb_db = os.environ.get('MONGODB_DB', 'shadowzap')
        
        # Connecting to MongoDB
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[mongodb_db]
        
        # Initializing collections for the database
        self.scans = self.db['scans']
        self.reports = self.db['reports']
        self.sessions = self.db['sessions']
        
        # GridFS is used for storing large files
        self.fs = gridfs.GridFS(self.db)
    
    # ----- Scan Management Methods -----
    def create_scan(self, target_url, scan_type, report_type="enhanced", report_format="html", web_session_id=None):
        """Create a new scan record"""
        scan_id = f"scan_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        scan = {
            "scan_id": scan_id,
            "target_url": target_url,
            "scan_type": scan_type,
            "status": "Initializing",
            "timestamp": datetime.utcnow(),
            "report_type": report_type,
            "report_format": report_format,
            "vulnerability_count": {
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            }
        }
        
        # Add web_session_id if provided
        if web_session_id:
            scan["web_session_id"] = web_session_id
            
            # Update session with this scan
            self.sessions.update_one(
                {"web_session_id": web_session_id},
                {
                    "$push": {"scans": scan_id},
                    "$inc": {"scan_count": 1},
                    "$set": {
                        "last_activity": datetime.utcnow(),
                        "target_url": target_url,
                        "scan_type": scan_type
                    }
                },
                upsert=True
            )
        
        result = self.scans.insert_one(scan)
        return scan_id
    
    def update_scan_status(self, scan_id, status, vulnerability_count=None):
        """Update scan status and related information"""
        update_data = {"status": status}
            
        if vulnerability_count:
            update_data["vulnerability_count"] = vulnerability_count
            
        result = self.scans.update_one(
            {"scan_id": scan_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    def get_scan(self, scan_id):
        """Get scan details by ID"""
        return self.scans.find_one({"scan_id": scan_id})
    
    def get_scan_by_task_id(self, task_id):
        """Get scan details by Celery task ID"""
        return self.scans.find_one({"task_id": task_id})
    
    # ----- Report Management Methods -----
    def save_report(self, scan_id, target_url, report_type, report_format, report_paths, web_session_id=None):
        """Save a scan report"""
        report_id = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Get scan details
        scan = self.get_scan(scan_id)
        scan_type = scan.get("scan_type", "") if scan else ""
        
        # Creating a document with metadata
        document = {
            "report_id": report_id,
            "scan_id": scan_id,
            "target_url": target_url,
            "report_type": report_type,
            "report_format": report_format,
            "timestamp": datetime.utcnow(),
            "scan_type": scan_type,
            "file_paths": {}
        }
        
        # Add web_session_id only if it's provided
        if web_session_id:
            document["web_session_id"] = web_session_id
            
            # Update session last activity
            self.sessions.update_one(
                {"web_session_id": web_session_id},
                {"$set": {"last_activity": datetime.utcnow()}}
            )
        
        # Getting the project root directory for relative path conversion
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Storing the file references and content
        for report_type_key, path in report_paths.items():
            if not path or not os.path.exists(path):
                continue
                
            # Converting the absolute path to a relative path for storage
            try:
                rel_path = os.path.relpath(path, project_root)
                document["file_paths"][report_type_key] = rel_path
            except ValueError:
                document["file_paths"][report_type_key] = path
            
            # Storing the file content in GridFS
            try:
                with open(path, 'rb') as file:
                    file_content = file.read()
                    
                    # Preparing the metadata for the report
                    metadata = {
                        "report_id": report_id,
                        "target_url": target_url,
                        "scan_type": scan_type,
                        "report_type": report_type
                    }
                    
                    # Add web_session_id to metadata only if it's provided and the report is saved
                    if web_session_id:
                        metadata["web_session_id"] = web_session_id
                    
                    # Store in GridFS with metadata
                    file_id = self.fs.put(
                        file_content, 
                        filename=os.path.basename(path),
                        content_type=self._get_content_type(report_type_key),
                        metadata=metadata
                    )
                    document["file_paths"][f"{report_type_key}_id"] = str(file_id)
            except Exception as e:
                print(f"Error storing file content for {path}: {e}")
        
        # Insert the report document
        self.reports.insert_one(document)
        
        # Update scan status to completed if the report is saved
        self.update_scan_status(scan_id, "Completed")
        
        return report_id
    
    def _get_content_type(self, report_type):
        """Get content type based on report type"""
        content_types = {
            "html": "text/html",
            "pdf": "application/pdf",
            "xml": "application/xml",
            "json": "application/json",
            "markdown": "text/markdown"
        }
        return content_types.get(report_type, "application/octet-stream")
    
    def get_report_file(self, file_id):
        """Get report file content from GridFS"""
        try:
            grid_out = self.fs.get(ObjectId(file_id))
            return grid_out.read()
        except Exception as e:
            print(f"Error retrieving file {file_id}: {e}")
            return None
    
    def get_report(self, report_id):
        """Get report details by ID"""
        return self.reports.find_one({"report_id": report_id})
    
    # ----- Session Management Methods -----
    def get_or_create_session(self, web_session_id, user_agent=None, ip_address=None):
        """Get or create a web session"""
        session = self.sessions.find_one({"web_session_id": web_session_id})
        
        if not session:
            session = {
                "web_session_id": web_session_id,
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "user_agent": user_agent,
                "ip_address": ip_address,
                "scan_count": 0,
                "scans": []
            }
            
            self.sessions.insert_one(session)
        else:
            # Update last activity
            self.sessions.update_one(
                {"web_session_id": web_session_id},
                {"$set": {"last_activity": datetime.utcnow()}}
            )
        
        return web_session_id