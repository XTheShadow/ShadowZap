@echo off
title ShadowZap

:: Start Redis in WSL
start cmd /k "wsl -d kali-linux -e redis-server"

:: Wait for Redis to start
timeout /t 3

:: Start Celery Worker
start cmd /k "celery -A app.services.celery_service worker --pool=solo --loglevel=info"

:: Wait for Celery to initialize
timeout /t 3

:: Start FastAPI
start cmd /k "uvicorn app.api.scan:app --reload --host 0.0.0.0 --port 8000"

:: Start Frontend
start cmd /k "cd FrontEnd/shadowzap-frontend && npm start"

echo All services started!