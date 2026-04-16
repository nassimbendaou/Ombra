#!/bin/bash
set -e
cd /home/azureuser/Ombra/frontend

echo "=== Removing ESM-only react-markdown v10 ==="
npm uninstall react-markdown remark-gfm --legacy-peer-deps 2>&1 | tail -5

echo "=== Installing CJS-compatible versions ==="
npm install react-markdown@8.0.7 remark-gfm@3.0.1 --legacy-peer-deps 2>&1 | tail -5

echo "=== Verifying versions ==="
cat node_modules/react-markdown/package.json | grep '"version"'
cat node_modules/remark-gfm/package.json | grep '"version"'

echo "=== Clearing cache ==="
rm -rf node_modules/.cache

echo "=== Building ==="
export NODE_OPTIONS='--max-old-space-size=1024'
/usr/bin/npx craco build 2>&1 | tail -20

echo "=== Checking build ==="
ls -la build/static/js/main.*.js
grep -c 'remarkGfm\|react-markdown\|ReactMarkdown' build/static/js/main.*.js && echo "react-markdown FOUND in build" || echo "react-markdown NOT found in build"
