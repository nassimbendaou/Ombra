#!/bin/bash
set -e
cd /home/azureuser/Ombra/frontend
export NODE_OPTIONS='--max-old-space-size=1024'
echo "Starting build at $(date)"
/usr/bin/npx craco build 2>&1
echo "Build completed at $(date)"
ls -la build/static/js/main.*.js
grep -c 'ReactMarkdown\|react-markdown\|remarkGfm' build/static/js/main.*.js && echo "react-markdown FOUND in build" || echo "react-markdown NOT found in build"
