#!/usr/bin/env bash
# =============================================================================
# setup_cloud.sh — Cloud environment bootstrap for news-analysis pipeline
#
# Fetches all secrets from Infisical using Machine Identity authentication,
# writes .env and config.yaml, then installs Python dependencies.
#
# Required environment variables (set as GitHub Secrets or exported locally):
#   INFISICAL_CLIENT_ID       — Machine Identity Client ID
#   INFISICAL_CLIENT_SECRET   — Machine Identity Client Secret
#   INFISICAL_PROJECT_ID      — Infisical project UUID
#
# Optional:
#   INFISICAL_ENV             — Secret environment to pull from (default: prod)
#   INFISICAL_SITE_URL        — Self-hosted Infisical URL (default: cloud)
# =============================================================================

set -euo pipefail

INFISICAL_ENV="${INFISICAL_ENV:-prod}"

# ---------------------------------------------------------------------------
# 1. Install Infisical CLI (skip if already present)
# ---------------------------------------------------------------------------
if ! command -v infisical &>/dev/null; then
  echo "[setup] Installing Infisical CLI..."
  if command -v apt-get &>/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' \
      | sudo -E bash
    sudo apt-get install -y infisical
  elif command -v brew &>/dev/null; then
    brew install infisical/get-cli/infisical
  else
    echo "[setup] ERROR: Cannot install Infisical CLI — unsupported package manager" >&2
    exit 1
  fi
fi

echo "[setup] Infisical CLI: $(infisical --version)"

# ---------------------------------------------------------------------------
# 2. Validate required credentials
# ---------------------------------------------------------------------------
: "${INFISICAL_CLIENT_ID:?INFISICAL_CLIENT_ID env var is required}"
: "${INFISICAL_CLIENT_SECRET:?INFISICAL_CLIENT_SECRET env var is required}"
: "${INFISICAL_PROJECT_ID:?INFISICAL_PROJECT_ID env var is required}"

# Infisical CLI reads these env vars for Machine Identity auth
export INFISICAL_MACHINE_IDENTITY_CLIENT_ID="$INFISICAL_CLIENT_ID"
export INFISICAL_MACHINE_IDENTITY_CLIENT_SECRET="$INFISICAL_CLIENT_SECRET"

SITE_ARGS=()
if [ -n "${INFISICAL_SITE_URL:-}" ]; then
  SITE_ARGS=(--domain "$INFISICAL_SITE_URL")
fi

echo "[setup] Fetching secrets from project $INFISICAL_PROJECT_ID (env: $INFISICAL_ENV)..."

# ---------------------------------------------------------------------------
# 3. Write .env from Infisical secrets (dotenv format)
# ---------------------------------------------------------------------------
infisical export \
  "${SITE_ARGS[@]}" \
  --projectId "$INFISICAL_PROJECT_ID" \
  --env "$INFISICAL_ENV" \
  --format dotenv \
  > .env

echo "[setup] .env written ($(wc -l < .env) lines)"

# ---------------------------------------------------------------------------
# 4. Write config.yaml from CONFIG_YAML secret
# ---------------------------------------------------------------------------
CONFIG_YAML_VALUE=$(
  infisical secrets get CONFIG_YAML \
    "${SITE_ARGS[@]}" \
    --projectId "$INFISICAL_PROJECT_ID" \
    --env "$INFISICAL_ENV" \
    --plain 2>/dev/null || true
)

if [ -n "$CONFIG_YAML_VALUE" ]; then
  printf '%s\n' "$CONFIG_YAML_VALUE" > config.yaml
  echo "[setup] config.yaml written from Infisical CONFIG_YAML secret"
elif [ -f config.yaml ]; then
  echo "[setup] CONFIG_YAML secret not found — using existing config.yaml"
else
  echo "[setup] ERROR: No config.yaml and CONFIG_YAML secret not found in Infisical" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. Install Python dependencies
# ---------------------------------------------------------------------------
echo "[setup] Installing Python dependencies..."
pip install --quiet --disable-pip-version-check -r requirements.txt

echo "[setup] Setup complete. Ready to run pipeline."
