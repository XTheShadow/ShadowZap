# ShadowZAP - Automated Penetration Testing Tool

An automated security testing framework that combines OWASP ZAP web vulnerability scanning, AI-powered risk assessment, and enhanced visual reporting.

## Features

- **Automated Vulnerability Scanning**: Leverages OWASP ZAP for comprehensive web security scanning
- **AI-Enhanced Analysis**: Uses LLM models to analyze and explain vulnerabilities in plain language
- **Visual Report Generation**: Creates professional PDF and HTML reports with charts and risk assessments
- **Multiple Scan Types**: Basic scans, full scans, API scans, and spider scans
- **Web Interface**: Modern React-based frontend for easy scan management
- **Asynchronous Processing**: Background task processing with Celery and Redis
- **Persistent Storage**: MongoDB for storing scan results and reports

## Prerequisites

- Docker and Docker Compose
- Python 3.8 or higher
- MongoDB
- Redis

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/XTheShadow/ShadowZap
cd ShadowZap
```

2. Configure environment variables:
- Create a `.env` file based on the `.testenv` template
- Update the environment variables with your configuration:
```
# Database Configuration
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=YOUR_DB_NAME

# Redis Configuration (for Celery)
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379

# Docker Configuration
ZAP_IMAGE=owasp/zap2docker-stable

# API Keys
Llama_API_KEY=your_llama_api_key_here
```

3. Install dependencies:
```bash
cd
pip install -r requirements.txt
```

4. Create required directories:
```bash
mkdir -p reports/outputs reports/final reports/zap_outputs reports/enhanced_reports
```

5. Start the services using Docker Compose:
```bash
docker-compose up -d
```

## Running the Application

1. Start the FastAPI server:
```bash
# On Windows
start_services.bat

# On Linux/Mac
1- Start the Redis server:
wsl -d kali-linux -e redis-server

2- Start the Celery worker for background tasks:
celery -A app.services.celery_service worker --loglevel=info

3- Start the FastAPI:
uvicorn app.api.scan:app --host 0.0.0.0 --port 8000 --reload

4- Start the Frontend:
cd FrontEnd/shadowzap-frontend && npm start
```

2. Access the web interface at: http://localhost:8000 (or your configured port)

## API Endpoints

### Scanning

- **Start a scan**: `POST /scan`
  ```bash
  curl -X POST http://localhost:8000/scan \
    -H "Content-Type: application/json" \
    -d '{"target_url": "https://example.com", "scan_type": "BASIC", "report_type": "ENHANCED", "report_format": "HTML"}'
  ```

- **Check scan status**: `GET /scan/{task_id}`
  ```bash
  curl http://localhost:8000/scan/your-task-id
  ```

### Reports

- **Get report file**: `GET /files/{file_id}`
- **Get direct file**: `GET /direct-files/{report_id}/{file_type}`
- **Get enhanced HTML report**: `GET /enhanced-html/{report_id}`
- **Get session HTML report**: `GET /session-reports/{session_id}/enhanced-html`
- **Get session PDF report**: `GET /session-reports/{session_id}/enhanced-pdf`

### Session Management

- **List files by session**: `GET /sessions/{session_id}/files`
- **List all sessions**: `GET /sessions`
- **Get dashboard statistics**: `GET /dashboard`

## Frontend Development

Navigate to the frontend directory and start the development server:

```bash
cd FrontEnd/shadowzap-frontend
npm install
npm start
```

## Development

- Run tests: `pytest tests/`
- Format code: `black app/`

## Project Structure

```
├── app/                    # Main application code
│   ├── api/                # API endpoints
│   ├── models/             # Data models
│   ├── services/           # Services (database, celery, etc.)
│   ├── tasks/              # Background tasks
│   └── utils/              # Utility functions
├── reports/                # Generated reports
│   ├── enhanced/           # Enhanced reports
│   ├── enhanced_reports/   # AI-enhanced reports
│   ├── final/              # Final reports
│   ├── outputs/            # Raw outputs
│   ├── templates/          # Report templates
│   └── zap_outputs/        # ZAP scanner outputs
├── FrontEnd/               # React frontend
├── setup/                  # Setup scripts
|── tests/                  # Test cases
|── requirements.txt
|── .env
|── .gitignore
└── start_services.bat


```

## License

This project is licensed under the MIT License - see the LICENSE file for details.