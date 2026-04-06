#!/bin/bash
set -e

# Deploy :backend to Cloud Run.
# Uses gcloud to build via Cloud Build (Dockerfile at repo root), push to
# Artifact Registry, and deploy — all in one step.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Active project set to 'bacons-law' (gcloud config set project bacons-law)
#   - TMDB_API_KEY secret exists in Secret Manager

gcloud run deploy bacons-law-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
