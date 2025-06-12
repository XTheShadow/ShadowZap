# A simple script to test the MongoDB database connection.

import os
import sys
import datetime
from ..app.services.database_service import DatabaseService

def test_connection():
    """Test the database connection and basic operations"""
    print("Testing MongoDB connection...")
    
    # Set environment variables for testing if not already set
    if not os.environ.get('MONGODB_URI'):
        print("Setting MONGODB_URI environment variable for testing")
        os.environ['MONGODB_URI'] = 'mongodb://localhost:27017/'
    
    if not os.environ.get('MONGODB_DB'):
        print("Setting MONGODB_DB environment variable for testing")
        os.environ['MONGODB_DB'] = 'shadowzap_test'
    
    try:
        # Create database service
        db_service = DatabaseService()
        print(f"✅ Connected to MongoDB at {os.environ.get('MONGODB_URI')}")
        print(f"✅ Using database: {os.environ.get('MONGODB_DB')}")
        
        # Test inserting a document
        test_doc = {
            'test_id': f'test_{datetime.datetime.now().timestamp()}',
            'message': 'This is a test document',
            'timestamp': datetime.datetime.utcnow()
        }
        
        result = db_service.reports_collection.insert_one(test_doc)
        print(f"✅ Inserted test document with ID: {result.inserted_id}")
        
        # Test retrieving the document
        retrieved = db_service.reports_collection.find_one({'_id': result.inserted_id})
        if retrieved:
            print(f"✅ Retrieved test document: {retrieved['message']}")
        else:
            print("❌ Failed to retrieve test document")
        
        # Clean up - delete the test document
        db_service.reports_collection.delete_one({'_id': result.inserted_id})
        print("✅ Deleted test document")
        
        print("\nMongoDB connection test completed successfully! 🎉")
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure MongoDB is running")
        print("2. Check that the connection URI is correct")
        print("3. Verify network connectivity to the MongoDB server")
        print("4. Ensure authentication credentials are correct (if using authentication)")
        return False

if __name__ == "__main__":
    test_connection() 