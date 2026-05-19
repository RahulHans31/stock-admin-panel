#!/bin/bash
# Script to pull environment variables from Vercel

echo "📥 Pulling environment variables from Vercel..."

# Pull production environment variables
vercel env pull .env.local

echo "✅ Environment variables saved to .env.local"
echo ""
echo "Now copy the relevant variables to .env:"
echo "cp .env.local .env"
