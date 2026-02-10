<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Eduvision CRM - Helen Doron Educational Group

This is a CRM application with Python (FastAPI) backend and React frontend, designed to be deployed via Coolify using Docker Compose.

## Architecture

- **Backend**: FastAPI (Python 3.11) running on port 8000
- **Frontend**: React + Vite served by Nginx on port 3000
- **Deployment**: Docker Compose ready for Coolify

## Quick Start with Docker

**Prerequisites:** Docker and Docker Compose

1. Build and run the application:
   ```bash
   docker-compose up --build
   ```

2. Access the application:
   - **Frontend**: http://localhost:3000
   - **Backend API**: http://localhost:3000/api/ (proxied through Nginx)
   - **Direct Backend**: http://localhost:8000 (if needed for debugging)

3. Test the backend health endpoint:
   ```bash
   curl http://localhost:3000/api/health
   ```

## Development Setup

### Backend Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

View your app in AI Studio: https://ai.studio/apps/drive/1lWEQEIBX-jRg-cw2HsRMraP2uCATqccO
