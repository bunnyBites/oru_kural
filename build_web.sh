#!/usr/bin/env bash
set -e

echo "Building Oru Kural frontend for web..."
cd frontend
dx build --release --platform web
echo "Build complete. Output: frontend/dist/"
echo "Deploy with: vercel --prod"
