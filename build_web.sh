#!/usr/bin/env bash
set -e

BACKEND_URL="${API_BASE_URL:-https://oru-kural-backend.fly.dev}"
OUT="frontend/target/dx/oru-kural-frontend/release/web/public"

echo "========================================="
echo "  Oru Kural — frontend build"
echo "  API_BASE_URL = $BACKEND_URL"
echo "========================================="

# Build WASM (API_BASE_URL is baked in at compile time via option_env!)
(cd frontend && API_BASE_URL="$BACKEND_URL" dx build --release)

# Write a minimal vercel.json into the output dir so the SPA rewrite
# travels with the deployment — Vercel picks this up when we deploy
# the directory directly (vercel <path> --prod).
cat > "$OUT/vercel.json" <<'EOF'
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
EOF

echo ""
echo "Build complete → $OUT"
echo ""
echo "Deploying to Vercel production..."
vercel "$OUT" --prod
