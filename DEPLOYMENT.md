# Deployment Guide - Eduvision CRM

## Quick Start with Docker Compose

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/eduvisionlviv/eduvision_crm.git
   cd eduvision_crm
   ```

2. **Build and start services**
   ```bash
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API health: http://localhost:3000/api/health
   - Direct backend (for debugging): http://localhost:8000

4. **Stop services**
   ```bash
   docker-compose down
   ```

### Production Deployment with Coolify

1. **Configure your Coolify server**
   - Connect your repository to Coolify
   - Coolify will automatically detect the `docker-compose.yml`

2. **Environment Variables (Optional)**
   
   For the backend service, you can set:
   - `ALLOWED_ORIGINS`: Comma-separated list of allowed CORS origins
     - Example: `https://yourdomain.com,https://www.yourdomain.com`
     - Default: `*` (allow all, not recommended for production)

3. **Deploy**
   - Coolify will build both services using the multi-stage Dockerfiles
   - Frontend will be accessible on your configured domain
   - API endpoints will be available at `/api/*`

### Testing the Deployment

After deployment, verify the services are running:

```bash
# Test backend health endpoint
curl http://localhost:3000/api/health
# Expected: {"status":"ok"}

# Check frontend is accessible
curl -I http://localhost:3000
# Expected: HTTP 200 OK
```

### Architecture Overview

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Nginx (port 3000)  │
│   Frontend Static   │
└──────┬──────────────┘
       │
       ├─► Serves React app files
       │
       └─► /api/* → Backend (port 8000)
                    │
                    ▼
             ┌────────────────┐
             │  FastAPI       │
             │  Python 3.11   │
             └────────────────┘
```

### Service Details

#### Backend (FastAPI)
- **Image**: Python 3.11-slim
- **Port**: 8000 (internal), exposed via frontend proxy
- **Health Check**: GET /api/health
- **Source**: `backend/`

#### Frontend (React + Nginx)
- **Build**: Node 20-alpine
- **Serve**: Nginx alpine
- **Port**: 3000 (mapped to Nginx port 80)
- **Source**: `frontend/`

### Troubleshooting

#### Services won't start
```bash
# Check Docker daemon is running
docker ps

# View service logs
docker-compose logs backend
docker-compose logs frontend

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

#### Frontend can't connect to backend
- Ensure both services are in the same Docker network
- Check `docker-compose.yml` network configuration
- Verify nginx.conf proxy configuration
- Check backend container logs: `docker-compose logs backend`

#### Port conflicts
If ports 3000 or 8000 are already in use:
```yaml
# Edit docker-compose.yml
services:
  backend:
    ports:
      - "8001:8000"  # Change host port
  frontend:
    ports:
      - "3001:80"    # Change host port
```

### Development Workflow

#### Backend Development
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Security Considerations

1. **CORS Configuration**
   - Set `ALLOWED_ORIGINS` environment variable in production
   - Never use `*` in production environments

2. **Environment Variables**
   - Use `.env` files for local development (not committed to git)
   - Use Coolify's environment variable management for production

3. **HTTPS**
   - Coolify provides automatic HTTPS via Let's Encrypt
   - Ensure your domain is properly configured

### Monitoring

Check service health:
```bash
# Backend health
curl http://localhost:3000/api/health

# Container status
docker-compose ps

# View real-time logs
docker-compose logs -f
```

### Scaling

To run multiple instances (Coolify handles this automatically):
```bash
docker-compose up --scale backend=3 --scale frontend=2
```

Note: You'll need a load balancer for multiple frontend instances.
