#!/usr/bin/env bash
# =============================================================================
# scripts/setup_cloud.sh
# Cloud environment setup using Infisical for secrets management.
#
# Required env vars (pass as GitHub Secrets or set before running):
#   INFISICAL_CLIENT_ID      — Universal Auth client ID
#   INFISICAL_CLIENT_SECRET  — Universal Auth client secret
#   INFISICAL_PROJECT_ID     — Infisical project ID
#
# What this script does:
#   1. Installs the Infisical CLI
#   2. Authenticates via Universal Auth (machine-to-machine)
#   3. Exports all project secrets as environment variables
#   4. Writes config.yaml from the CONFIG_YAML secret
#   5. Installs Python dependencies
# =============================================================================

set -euo pipefail

echo "=== News Analysis Cloud Setup ==="

# --- Validate required variables ---
: "${INFISICAL_CLIENT_ID:?ERROR: INFISICAL_CLIENT_ID is not set}"
: "${INFISICAL_CLIENT_SECRET:?ERROR: INFISICAL_CLIENT_SECRET is not set}"
: "${INFISICAL_PROJECT_ID:?ERROR: INFISICAL_PROJECT_ID is not set}"

# --- 1. Install Infisical CLI ---
echo "[1/5] Installing Infisical CLI..."
if ! command -v infisical &>/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' \
    | sudo -E bash
  sudo apt-get install -y infisical
  echo "Infisical CLI installed: $(infisical --version)"
else
  echo "Infisical CLI already present: $(infisical --version)"
fi

# --- 2. Authenticate via Universal Auth and obtain token ---
echo "[2/5] Authenticating with Infisical (Universal Auth)..."
INFISICAL_TOKEN=$(infisical login \
  --method=universal-auth \
  --client-id="${INFISICAL_CLIENT_ID}" \
  --client-secret="${INFISICAL_CLIENT_SECRET}" \
  --silent \
  --plain)

if [ -z "${INFISICAL_TOKEN}" ]; then
  echo "ERROR: Failed to obtain Infisical token" >&2
  exit 1
fi
export INFISICAL_TOKEN
# Persist token for subsequent GitHub Actions steps
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "INFISICAL_TOKEN=${INFISICAL_TOKEN}" >> "${GITHUB_ENV}"
fi
echo "Authentication successful."

# --- 3. Export secrets as environment variables ---
echo "[3/5] Exporting secrets from Infisical (project: ${INFISICAL_PROJECT_ID})..."
SECRETS_DOTENV=$(infisical export \
  --projectId="${INFISICAL_PROJECT_ID}" \
  --env=prod \
  --format=dotenv-export)

# Write to a temp file and source it so secrets enter the current shell
SECRETS_FILE=$(mktemp)
echo "${SECRETS_DOTENV}" > "${SECRETS_FILE}"
# shellcheck source=/dev/null
source "${SECRETS_FILE}"
rm -f "${SECRETS_FILE}"
echo "Secrets loaded into environment."

# Persist all non-sensitive exports to GITHUB_ENV for subsequent steps
# (CONFIG_YAML is handled separately below; token already exported above)
if [ -n "${GITHUB_ENV:-}" ]; then
  infisical export \
    --projectId="${INFISICAL_PROJECT_ID}" \
    --env=prod \
    --format=dotenv \
    >> "${GITHUB_ENV}"
fi

# --- 4. Write config.yaml from the CONFIG_YAML secret ---
echo "[4/5] Writing config.yaml..."
if [ -z "${CONFIG_YAML:-}" ]; then
  echo "ERROR: CONFIG_YAML secret is empty or not set in Infisical" >&2
  exit 1
fi
printf '%s' "${CONFIG_YAML}" > config.yaml
echo "config.yaml written ($(wc -l < config.yaml) lines)."

# --- 5. Install Python dependencies ---
echo "[5/5] Installing Python dependencies..."
pip install --quiet -r requirements.txt
echo "Dependencies installed."

echo ""
echo "=== Setup complete. Environment is ready. ==="
