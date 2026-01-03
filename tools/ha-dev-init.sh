#!/bin/bash
set -e

CONFIG_DIR="/config"
STORAGE_DIR="${CONFIG_DIR}/.storage"

echo "🚀 Initializing Home Assistant development environment..."

# Check if already initialized
if [ -f "${STORAGE_DIR}/.dev-initialized" ]; then
    echo "✅ Already initialized, skipping setup"
    exit 0
fi

echo "📁 Creating storage directory..."
mkdir -p "${STORAGE_DIR}"

# Create onboarding file to skip wizard
echo "⏭️  Skipping onboarding wizard..."
cat > "${STORAGE_DIR}/onboarding" <<'EOF'
{
  "version": 4,
  "minor_version": 1,
  "key": "onboarding",
  "data": {
    "done": [
      "user",
      "core_config",
      "integration",
      "analytics"
    ]
  }
}
EOF

# Create core.config_entries for analytics
echo "📊 Configuring analytics..."
cat > "${STORAGE_DIR}/core.config_entries" <<'EOF'
{
  "version": 1,
  "minor_version": 1,
  "key": "core.config_entries",
  "data": {
    "entries": []
  }
}
EOF

# Create person storage
echo "👤 Creating person storage..."
cat > "${STORAGE_DIR}/person" <<'EOF'
{
  "version": 2,
  "minor_version": 2,
  "key": "person",
  "data": {
    "persons": [],
    "config_entry_persons": []
  }
}
EOF

# Note: We skip creating the auth files here because proper password hashing
# requires Python's bcrypt library which isn't available in the HA container yet.
# Instead, we let HA handle user creation on first access, but with all other
# onboarding steps skipped.

echo "ℹ️  User creation will be handled by Home Assistant on first access"
echo "   (Onboarding wizard is still skipped - just create your user)"

# Create basic configuration.yaml if it doesn't exist
if [ ! -f "${CONFIG_DIR}/configuration.yaml" ]; then
    echo "📝 Creating configuration.yaml..."
    cat > "${CONFIG_DIR}/configuration.yaml" <<'EOF'
# Home Assistant Development Configuration

default_config:

# Enable logging
logger:
  default: info
  logs:
    custom_components.melcloudhome: debug

# Development tools
api:
developer_tools:

# Text to speech (for testing)
tts:
  - platform: google_translate
EOF
fi

# Create secrets.yaml if needed
if [ ! -f "${CONFIG_DIR}/secrets.yaml" ]; then
    echo "🔒 Creating secrets.yaml..."
    cat > "${CONFIG_DIR}/secrets.yaml" <<'EOF'
# Development secrets file
# Add your MELCloud credentials here for testing
# melcloud_email: test@example.com
# melcloud_password: test123
EOF
fi

# Mark as initialized
touch "${STORAGE_DIR}/.dev-initialized"

echo "✅ Home Assistant development environment initialized!"
echo "📍 Admin credentials: ${HASS_USERNAME:-dev} / ${HASS_PASSWORD:-dev}"
echo "🌐 Mock MELCloud API: http://melcloud-mock:8080"
echo ""
