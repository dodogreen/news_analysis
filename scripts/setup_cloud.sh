#!/usr/bin/env bash
# setup_cloud.sh — Bootstrap cloud environment via Infisical secrets manager.
#
# Usage (source so that exported vars are available in the caller's shell):
#   source scripts/setup_cloud.sh
#
# Required environment variables (set these before sourcing):
#   INFISICAL_CLIENT_ID       — Infisical machine identity client ID
#   INFISICAL_CLIENT_SECRET   — Infisical machine identity client secret
#   INFISICAL_PROJECT_ID      — Infisical project ID
#
# Optional:
#   INFISICAL_ENV             — Infisical environment slug (default: prod)
#
# What this script does:
#   1. Installs the Infisical CLI if not already present
#   2. Authenticates with machine identity credentials
#   3. Exports all project secrets as environment variables
#   4. Writes config.yaml from the CONFIG_YAML secret
#   5. Installs Python dependencies

set -euo pipefail

INFISICAL_ENV="${INFISICAL_ENV:-prod}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_info()  { echo "[setup_cloud] $*"; }
_error() { echo "[setup_cloud] ERROR: $*" >&2; }

_require_var() {
    local var="$1"
    if [[ -z "${!var:-}" ]]; then
        _error "Required environment variable \$${var} is not set."
        return 1
    fi
}

# ---------------------------------------------------------------------------
# 1. Validate required vars
# ---------------------------------------------------------------------------
_require_var INFISICAL_CLIENT_ID
_require_var INFISICAL_CLIENT_SECRET
_require_var INFISICAL_PROJECT_ID

# ---------------------------------------------------------------------------
# 2. Install Infisical CLI if needed
# ---------------------------------------------------------------------------
if ! command -v infisical &>/dev/null; then
    _info "Infisical CLI not found — installing..."

    if command -v apt-get &>/dev/null; then
        # Debian / Ubuntu
        curl -1sLf \
            'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' \
            | sudo -E bash
        sudo apt-get install -y infisical
    elif command -v brew &>/dev/null; then
        # macOS
        brew install infisical/get-cli/infisical
    else
        _error "Unsupported OS — install Infisical CLI manually: https://infisical.com/docs/cli/overview"
        return 1
    fi
    _info "Infisical CLI installed: $(infisical --version)"
else
    _info "Infisical CLI already present: $(infisical --version)"
fi

# ---------------------------------------------------------------------------
# 3. Authenticate and obtain token
# ---------------------------------------------------------------------------
_info "Authenticating with Infisical machine identity..."
INFISICAL_TOKEN=$(infisical login \
    --method=universal-auth \
    --client-id="${INFISICAL_CLIENT_ID}" \
    --client-secret="${INFISICAL_CLIENT_SECRET}" \
    --plain \
    --silent)
export INFISICAL_TOKEN
_info "Authentication successful."

# ---------------------------------------------------------------------------
# 4. Export secrets as environment variables
# ---------------------------------------------------------------------------
_info "Exporting secrets from project ${INFISICAL_PROJECT_ID} (env: ${INFISICAL_ENV})..."
eval "$(infisical export \
    --token="${INFISICAL_TOKEN}" \
    --projectId="${INFISICAL_PROJECT_ID}" \
    --env="${INFISICAL_ENV}" \
    --format=dotenv-export \
    --silent)"
_info "Secrets exported."

# ---------------------------------------------------------------------------
# 5. Write config.yaml from CONFIG_YAML secret
# ---------------------------------------------------------------------------
if [[ -n "${CONFIG_YAML:-}" ]]; then
    _info "Writing config.yaml from Infisical secret..."
    printf '%s\n' "${CONFIG_YAML}" > config.yaml
    _info "config.yaml written ($(wc -l < config.yaml | tr -d ' ') lines)."
else
    _error "CONFIG_YAML secret not found in Infisical — config.yaml was not written."
fi

# ---------------------------------------------------------------------------
# 6. Install Python dependencies
# ---------------------------------------------------------------------------
if [[ -f requirements.txt ]]; then
    _info "Installing Python dependencies..."
    pip install -q -r requirements.txt
    _info "Dependencies installed."
fi

_info "Setup complete. Environment is ready."
