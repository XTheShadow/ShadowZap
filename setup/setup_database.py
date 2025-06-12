import sys
import os
from pymongo import MongoClient, IndexModel, ASCENDING, TEXT
from datetime import datetime
from dotenv import load_dotenv

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def setup_database():
    """Set up required collections for the Automated Penetration Testing project"""
    # Set environment variables for MongoDB connection
    os.environ['MONGODB_URI'] = 'mongodb://localhost:27017/'
    os.environ['MONGODB_DB'] = 'shadowzap'
    
    try:
        # Connect to MongoDB
        client = MongoClient(os.environ.get('MONGODB_URI'))
        db = client[os.environ.get('MONGODB_DB')]
        
        print("Setting up collections in the shadowzap database...")
        
        # Generate IDs for sample data
        scan_id = "scan_" + datetime.now().strftime("%Y%m%d%H%M%S")
        web_session_id = "session_" + datetime.now().strftime("%Y%m%d%H%M%S")
        
        # 1. Scans Collection - Stores information about individual scans
        if "scans" not in db.list_collection_names():
            db.create_collection("scans")
            print("✅ Created 'scans' collection")
            
            # Create indexes for scans collection
            db.scans.create_index([("target_url", ASCENDING)])
            db.scans.create_index([("status", ASCENDING)])
            db.scans.create_index([("timestamp", ASCENDING)])
            db.scans.create_index([("scan_type", ASCENDING)])
            db.scans.create_index([("web_session_id", ASCENDING)])
            print("✅ Created indexes for 'scans' collection")
            
            # Insert sample scan
            db.scans.insert_one({
                "scan_id": scan_id,
                "target_url": "https://example.com",
                "scan_type": "basic",
                "status": "completed",
                "timestamp": datetime.utcnow(),
                "duration": 120,
                "ports_scanned": "1-1000",
                "report_type": "enhanced",
                "report_format": "html",
                "web_session_id": web_session_id,
                "vulnerability_count": {
                    "high": 1,
                    "medium": 2,
                    "low": 3,
                    "info": 4
                }
            })
            print("✅ Inserted sample document in 'scans' collection")
        else:
            print("⚠️ 'scans' collection already exists")
            
        # 2. Sessions Collection - Stores web session information
        if "sessions" not in db.list_collection_names():
            db.create_collection("sessions")
            print("✅ Created 'sessions' collection")
            
            # Create indexes for sessions collection
            db.sessions.create_index([("web_session_id", ASCENDING)], unique=True)
            db.sessions.create_index([("created_at", ASCENDING)])
            db.sessions.create_index([("last_activity", ASCENDING)])
            print("✅ Created indexes for 'sessions' collection")
            
            # Insert sample session
            db.sessions.insert_one({
                "web_session_id": web_session_id,
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "ip_address": "127.0.0.1",
                "scan_count": 1,
                "scans": [scan_id]
            })
            print("✅ Inserted sample document in 'sessions' collection")
        else:
            print("⚠️ 'sessions' collection already exists")
            
        # 3. Reports Collection - Stores generated reports
        if "reports" not in db.list_collection_names():
            db.create_collection("reports")
            print("✅ Created 'reports' collection")
            
            # Create indexes for reports collection
            db.reports.create_index([("scan_id", ASCENDING)])
            db.reports.create_index([("target_url", ASCENDING)])
            db.reports.create_index([("timestamp", ASCENDING)])
            print("✅ Created indexes for 'reports' collection")
            
            # Insert sample report
            db.reports.insert_one({
                "report_id": "report_" + datetime.now().strftime("%Y%m%d%H%M%S"),
                "scan_id": scan_id,
                "target_url": "https://example.com",
                "report_type": "enhanced",
                "report_format": "html",
                "timestamp": datetime.utcnow(),
                "web_session_id": web_session_id,
                "summary": {
                    "vulnerability_count": {
                        "high": 1,
                        "medium": 2,
                        "low": 3,
                        "info": 4
                    },
                    "scan_duration": 120,
                    "scan_type": "basic"
                },
                "file_paths": {
                    "html": "/reports/zap_outputs/zap_report_20250530_120000.html",
                    "xml": "/reports/zap_outputs/zap_report_20250530_120000.xml",
                    "json": "/reports/zap_outputs/zap_report_20250530_120000.json",
                    "markdown": "/reports/outputs/zap_report_20250530_120000.md"
                },
                "ai_analysis_performed": True,
                "ai_analysis_summary": "The scan detected 1 high severity SQL injection vulnerability that requires immediate attention."
            })
            print("✅ Inserted sample document in 'reports' collection")
        else:
            print("⚠️ 'reports' collection already exists")
            
        # 4. Settings Collection - Stores application settings
        if "settings" not in db.list_collection_names():
            db.create_collection("settings")
            print("✅ Created 'settings' collection")
            
            # Insert default settings
            db.settings.insert_one({
                "setting_id": "global_settings",
                "zap_image": "owasp/zap2docker-stable",
                "default_scan_type": "basic",
                "default_report_type": "enhanced",
                "default_report_format": "html",
                "default_port_range": "1-1000",
                "default_timeout": 60,
                "max_concurrent_scans": 5,
                "retention_period_days": 90,
                "notification_email": "admin@example.com",
                "session_timeout_minutes": 30,
                "last_updated": datetime.utcnow()
            })
            print("✅ Inserted default settings")
        else:
            print("⚠️ 'settings' collection already exists")
        
        # List all collections to verify
        collections = db.list_collection_names()
        print(f"\nCollections in shadowzap database: {collections}")
        
        print("\nMongoDB database setup completed successfully! 🎉")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

if __name__ == "__main__":
    setup_database() 