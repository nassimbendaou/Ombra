#!/bin/bash

# Ombra Application Startup Script
# This script starts both the backend and frontend servers

cd /home/azureuser/Ombra

echo "Starting Ombra Application..."
echo "=============================="

# Start Backend Server
echo "[1/2] Starting Python Backend Server..."
source venv/bin/activate
python backend/server.py > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait a moment for backend to start
sleep 3

# Start Frontend Development Server  
echo "[2/2] Starting React Frontend Server..."
cd /home/azureuser/Ombra/frontend
npm start > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "=============================="
echo "Application Started!"
echo "Backend:  http://20.67.232.113:8000 (or configured port)"
echo "Frontend: http://20.67.232.113:3000"
echo ""
echo "View logs:"
echo "  Backend:  tail -f /tmp/backend.log"
echo "  Frontend: tail -f /tmp/frontend.log"
echo ""
echo "Stop services:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
