#!/usr/bin/env bash
set -e

echo "Building Oru Kural frontend for web..."
cd frontend
dx build --release
echo "Build complete. Output: frontend/target/dx/oru-kural-frontend/release/web/public/"
echo "Deploy with: vercel --prod"
