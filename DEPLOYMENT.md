# Ombra - Azure VPS Deployment Guide

Complete guide to deploy Ombra autonomous AI agent system on Azure Virtual Private Server.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Azure VPS Setup](#azure-vps-setup)
3. [Server Configuration](#server-configuration)
4. [Application Deployment](#application-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Service Setup](#service-setup)
7. [SSL/HTTPS Configuration](#sslhttps-configuration)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts & Credentials
- **Azure Account** with active subscription
- **Emergent LLM Key** (for OpenAI/Anthropic/Google access)
- **Telegram Bot Token** (optional, for remote control)
- **Domain Name** (optional, for production deployment)

### Local Requirements
- SSH client
- Git (for code transfer)

---

## Azure VPS Setup

### 1. Create Ubuntu VM

**Option A: Azure Portal**
1. Navigate to Azure Portal → Virtual Machines → Create
2. Configure VM:
   - **Image:** Ubuntu 22.04 LTS
   - **Size:** Standard_B2s (2 vCPUs, 4 GB RAM) minimum
   - **Recommended:** Standard_D2s_v3 (2 vCPUs, 8 GB RAM)
   - **Authentication:** SSH public key
   - **Inbound Ports:** 22 (SSH), 80 (HTTP), 443 (HTTPS)
3. Review + Create

**Option B: Azure CLI**
```bash
# Login to Azure
az login

# Create resource group
az group create --name ombra-rg --location eastus

# Create VM
az vm create \
  --resource-group ombra-rg \
  --name ombra-vm \
  --image Ubuntu2204 \
  --size Standard_D2s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard

# Open ports
az vm open-port --resource-group ombra-rg --name ombra-vm --port 80 --priority 1000
az vm open-port --resource-group ombra-rg --name ombra-vm --port 443 --priority 1001
```

### 2. Get VM IP Address
```bash
az vm show --resource-group ombra-rg --name ombra-vm --show-details --query publicIps -o tsv
```

### 3. Connect to VM
```bash
ssh azureuser@<YOUR_VM_IP>
```

---

## Server Configuration

### 1. Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Required Packages
```bash
# System utilities
sudo apt install -y curl wget git build-essential python3-pip python3-venv

# Node.js 20.x (for frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installations
node --version  # Should be v20.x
npm --version
python3 --version
```

### 3. Install MongoDB
```bash
# Import MongoDB GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
   sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
   sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install MongoDB
sudo apt update
sudo apt install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify
sudo systemctl status mongod
```

### 4. Install Ollama (Local LLM)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
sudo systemctl start ollama
sudo systemctl enable ollama

# Pull required models
ollama pull mistral
ollama pull tinyllama

# Verify
ollama list
```

### 5. Install Nginx (Reverse Proxy)
```bash
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 6. Install Supervisor (Process Manager)
```bash
sudo apt install -y supervisor
sudo systemctl start supervisor
sudo systemctl enable supervisor
```

---

## Application Deployment

### 1. Create Application Directory
```bash
sudo mkdir -p /opt/ombra
sudo chown $USER:$USER /opt/ombra
cd /opt/ombra
```

### 2. Clone/Upload Application Code

**Option A: From Git Repository**
```bash
git clone <YOUR_REPO_URL> .
```

**Option B: Upload via SCP (from local machine)**
```bash
# From your local machine
scp -r /path/to/ombra/* azureuser@<VM_IP>:/opt/ombra/
```

**Option C: Upload as Archive**
```bash
# On local machine
tar -czf ombra.tar.gz /path/to/ombra
scp ombra.tar.gz azureuser@<VM_IP>:~/

# On VM
cd /opt/ombra
tar -xzf ~/ombra.tar.gz --strip-components=1
```

### 3. Install Backend Dependencies
```bash
cd /opt/ombra/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Optional integrations (safe to skip if unavailable in your index)
pip install -r requirements-optional.txt
```

### 4. Install Frontend Dependencies
```bash
cd /opt/ombra/frontend

# Install packages (use npm or yarn)
npm install
# OR
# yarn install
```

### 5. Build Frontend for Production
```bash
cd /opt/ombra/frontend
npm run build
# OR
# yarn build

# This creates /opt/ombra/frontend/build directory
```

---

## Environment Configuration

### 1. Backend Environment Variables
```bash
cd /opt/ombra/backend
nano .env
```

Add the following:
```env
# MongoDB
MONGO_URL=mongodb://localhost:27017
DB_NAME=ombra_production

# Emergent LLM Key (Universal key for OpenAI/Anthropic/Google)
EMERGENT_LLM_KEY=your_emergent_key_here

# Ollama
OLLAMA_URL=http://localhost:11434

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Server
CORS_ORIGINS=*
```

**Security Note:** For production, restrict CORS_ORIGINS to your domain.

### 2. Frontend Environment Variables
```bash
cd /opt/ombra/frontend
nano .env.production
```

Add the following:
```env
REACT_APP_BACKEND_URL=http://localhost
```

**For Custom Domain:**
```env
REACT_APP_BACKEND_URL=https://yourdomain.com
```

### 3. Rebuild Frontend with Production Config
```bash
cd /opt/ombra/frontend
npm run build
```

---

## Service Setup

### 1. Configure Supervisor for Backend

Create backend service config:
```bash
sudo nano /etc/supervisor/conf.d/ombra-backend.conf
```

Add:
```ini
[program:ombra-backend]
directory=/opt/ombra/backend
command=/opt/ombra/backend/venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8001
user=azureuser
autostart=true
autorestart=true
stderr_logfile=/var/log/ombra/backend.err.log
stdout_logfile=/var/log/ombra/backend.out.log
environment=PATH="/opt/ombra/backend/venv/bin"
```

### 2. Configure Supervisor for Frontend

Create frontend service config:
```bash
sudo nano /etc/supervisor/conf.d/ombra-frontend.conf
```

Add:
```ini
[program:ombra-frontend]
directory=/opt/ombra/frontend
command=/usr/bin/npx serve -s build -l 3000
user=azureuser
autostart=true
autorestart=true
stderr_logfile=/var/log/ombra/frontend.err.log
stdout_logfile=/var/log/ombra/frontend.out.log
```

### 3. Create Log Directory
```bash
sudo mkdir -p /var/log/ombra
sudo chown azureuser:azureuser /var/log/ombra
```

### 4. Start Services
```bash
# Reload supervisor configuration
sudo supervisorctl reread
sudo supervisorctl update

# Start services
sudo supervisorctl start ombra-backend
sudo supervisorctl start ombra-frontend

# Check status
sudo supervisorctl status
```

---

## Nginx Configuration

### 1. Create Nginx Site Configuration

**For IP-based access:**
```bash
sudo nano /etc/nginx/sites-available/ombra
```

Add:
```nginx
server {
    listen 80;
    server_name _;  # Matches any IP

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

**For domain-based access:**
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

### 2. Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/ombra /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

### 3. Access Application
```
http://<YOUR_VM_IP>
```

---

## SSL/HTTPS Configuration

### 1. Install Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Obtain SSL Certificate
```bash
# Make sure DNS points to your VM IP first
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts. Certbot will automatically:
- Obtain SSL certificate
- Configure Nginx for HTTPS
- Set up auto-renewal

### 3. Test Auto-Renewal
```bash
sudo certbot renew --dry-run
```

### 4. Access Secure Application
```
https://yourdomain.com
```

---

## Monitoring & Maintenance

### 1. Check Service Status
```bash
# All services
sudo supervisorctl status

# Nginx
sudo systemctl status nginx

# MongoDB
sudo systemctl status mongod

# Ollama
sudo systemctl status ollama
```

### 2. View Logs
```bash
# Backend logs
tail -f /var/log/ombra/backend.out.log
tail -f /var/log/ombra/backend.err.log

# Frontend logs
tail -f /var/log/ombra/frontend.out.log
tail -f /var/log/ombra/frontend.err.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 3. Restart Services
```bash
# Backend only
sudo supervisorctl restart ombra-backend

# Frontend only
sudo supervisorctl restart ombra-frontend

# All services
sudo supervisorctl restart all

# Nginx
sudo systemctl restart nginx
```

### 4. Update Application
```bash
cd /opt/ombra

# Pull latest code
git pull

# Update backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-optional.txt

# Update frontend
cd ../frontend
npm install
npm run build

# Restart services
sudo supervisorctl restart all
```

### 5. Database Backup
```bash
# Create backup directory
mkdir -p /opt/ombra/backups

# Backup MongoDB
mongodump --db ombra_production --out /opt/ombra/backups/$(date +%Y%m%d_%H%M%S)

# Compress backup
cd /opt/ombra/backups
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz $(date +%Y%m%d_%H%M%S)
```

### 6. Restore Database
```bash
# Extract backup
cd /opt/ombra/backups
tar -xzf backup_YYYYMMDD_HHMMSS.tar.gz

# Restore
mongorestore --db ombra_production YYYYMMDD_HHMMSS/ombra_production
```

---

## Troubleshooting

### Backend Won't Start
```bash
# Check logs
tail -n 100 /var/log/ombra/backend.err.log

# Common issues:
# 1. Missing dependencies
cd /opt/ombra/backend
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-optional.txt

# 2. Port already in use
sudo lsof -i :8001
sudo kill -9 <PID>

# 3. MongoDB not running
sudo systemctl status mongod
sudo systemctl start mongod
```

### Frontend Won't Start
```bash
# Check logs
tail -n 100 /var/log/ombra/frontend.err.log

# Rebuild
cd /opt/ombra/frontend
npm run build
sudo supervisorctl restart ombra-frontend
```

### Ollama Models Not Loading
```bash
# Check Ollama status
sudo systemctl status ollama

# Restart Ollama
sudo systemctl restart ollama

# Re-pull models
ollama pull mistral
ollama pull tinyllama
```

### High Memory Usage
```bash
# Check memory
free -h

# Check processes
top
htop  # if installed

# Restart services to free memory
sudo supervisorctl restart all
```

### Nginx 502 Bad Gateway
```bash
# Check backend is running
sudo supervisorctl status ombra-backend

# Check backend port
curl http://localhost:8001/api/health

# Restart backend
sudo supervisorctl restart ombra-backend
```

### SSL Certificate Issues
```bash
# Renew certificate
sudo certbot renew

# Force renewal
sudo certbot renew --force-renewal

# Check certificate
sudo certbot certificates
```

---

## Performance Optimization

### 1. Enable Nginx Caching
Add to nginx config:
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=app_cache:10m max_size=1g inactive=60m;

location / {
    proxy_cache app_cache;
    proxy_cache_valid 200 10m;
    # ... other proxy settings
}
```

### 2. Enable Gzip Compression
Add to nginx config:
```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;
```

### 3. Increase Worker Processes
Edit `/etc/nginx/nginx.conf`:
```nginx
worker_processes auto;
worker_connections 1024;
```

### 4. MongoDB Performance
```bash
# Create indexes
mongosh
use ombra_production
db.tasks.createIndex({ "status": 1, "created_at": -1 })
db.memories.createIndex({ "type": 1, "pinned": 1 })
db.activity_log.createIndex({ "timestamp": -1, "type": 1 })
```

---

## Security Hardening

### 1. Firewall Setup
```bash
# Install UFW
sudo apt install -y ufw

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Enable firewall
sudo ufw enable
sudo ufw status
```

### 2. Fail2Ban (SSH Protection)
```bash
# Install
sudo apt install -y fail2ban

# Configure
sudo nano /etc/fail2ban/jail.local
```

Add:
```ini
[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
```

```bash
# Start service
sudo systemctl start fail2ban
sudo systemctl enable fail2ban
```

### 3. Secure MongoDB
```bash
# Edit MongoDB config
sudo nano /etc/mongod.conf
```

Add:
```yaml
security:
  authorization: enabled

net:
  bindIp: 127.0.0.1
```

```bash
# Create admin user
mongosh
use admin
db.createUser({
  user: "admin",
  pwd: "secure_password_here",
  roles: [ { role: "userAdminAnyDatabase", db: "admin" } ]
})

# Restart MongoDB
sudo systemctl restart mongod
```

### 4. Environment Variables Security
```bash
# Restrict .env file permissions
chmod 600 /opt/ombra/backend/.env
chmod 600 /opt/ombra/frontend/.env.production
```

---

## Cost Optimization

### Azure VM Sizing Recommendations

| Workload | VM Size | vCPUs | RAM | Monthly Cost (Est.) |
|----------|---------|-------|-----|---------------------|
| Development/Testing | Standard_B1s | 1 | 1 GB | ~$8 |
| Small Production | Standard_B2s | 2 | 4 GB | ~$30 |
| **Recommended** | Standard_D2s_v3 | 2 | 8 GB | ~$70 |
| High Performance | Standard_D4s_v3 | 4 | 16 GB | ~$140 |

### Cost-Saving Tips
1. **Use Azure Reserved Instances** - Save up to 72% with 1-3 year commitments
2. **Auto-shutdown** - Schedule VM shutdown during non-business hours
3. **Azure Hybrid Benefit** - Use existing Windows Server licenses
4. **Monitor resource usage** - Right-size VM based on actual usage

---

## Support & Resources

### Ombra Documentation
- GitHub Repository: `<YOUR_REPO_URL>`
- Issues: `<YOUR_REPO_URL>/issues`

### Azure Resources
- [Azure VM Documentation](https://docs.microsoft.com/azure/virtual-machines/)
- [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
- [Azure Support](https://azure.microsoft.com/support/)

### Community Support
- Ollama: https://github.com/ollama/ollama
- MongoDB: https://www.mongodb.com/docs/
- Nginx: https://nginx.org/en/docs/

---

## Quick Reference Commands

```bash
# Start all services
sudo supervisorctl start all

# Stop all services
sudo supervisorctl stop all

# Restart all services
sudo supervisorctl restart all

# View service status
sudo supervisorctl status

# View backend logs
tail -f /var/log/ombra/backend.err.log

# View frontend logs
tail -f /var/log/ombra/frontend.err.log

# Restart Nginx
sudo systemctl restart nginx

# Check MongoDB
sudo systemctl status mongod

# Backup database
mongodump --db ombra_production --out ~/backup_$(date +%Y%m%d)

# Check disk space
df -h

# Check memory usage
free -h

# Monitor processes
htop
```

---

## Deployment Checklist

- [ ] Azure VM created and accessible via SSH
- [ ] System packages updated
- [ ] Node.js 20.x installed
- [ ] Python 3 and pip installed
- [ ] MongoDB installed and running
- [ ] Ollama installed with models (mistral, tinyllama)
- [ ] Nginx installed and configured
- [ ] Supervisor installed
- [ ] Application code uploaded to `/opt/ombra`
- [ ] Backend dependencies installed
- [ ] Frontend built for production
- [ ] Environment variables configured (.env files)
- [ ] Supervisor services configured and running
- [ ] Nginx reverse proxy configured
- [ ] Application accessible via HTTP
- [ ] SSL certificate obtained (if using domain)
- [ ] Firewall configured (UFW)
- [ ] Fail2Ban configured
- [ ] Database backups scheduled
- [ ] Monitoring set up

---

**Deployment Complete! 🎉**

Access your Ombra instance at:
- **HTTP:** `http://<YOUR_VM_IP>`
- **HTTPS:** `https://yourdomain.com` (if SSL configured)

For support, consult the troubleshooting section or open an issue on GitHub.
