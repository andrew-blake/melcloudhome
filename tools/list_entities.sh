#!/bin/bash
# List and inspect MELCloud Home entities via Home Assistant API
# Usage: ./tools/list_entities.sh [climate|sensor|binary_sensor|all]

set -e

# Load environment
if [ -f .env ]; then
    source .env
else
    echo "❌ .env file not found"
    exit 1
fi

# Check required variables
if [ -z "$HA_URL" ] || [ -z "$HA_TOKEN" ]; then
    echo "❌ HA_URL and HA_TOKEN must be set in .env"
    exit 1
fi

PLATFORM="${1:-all}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Fetching MELCloud entities from Home Assistant...${NC}"
echo ""

# Get all states and filter for melcloud entities
STATES=$(curl -s -k -X GET "$HA_URL/api/states" \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json")

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to fetch states from Home Assistant${NC}"
    exit 1
fi

# Function to display entity details
show_entity() {
    local entity_id="$1"
    local entity_data=$(echo "$STATES" | grep -o "\"entity_id\":\"$entity_id\"[^}]*}" | head -1)

    if [ -z "$entity_data" ]; then
        echo -e "${RED}  ❌ Not found${NC}"
        return
    fi

    # Extract state
    local state=$(echo "$entity_data" | grep -o '"state":"[^"]*"' | cut -d'"' -f4)

    # Check if available (not in error/unavailable state)
    if [ "$state" = "unavailable" ]; then
        echo -e "${RED}  ⚠ State: unavailable${NC}"
    elif [ "$state" = "unknown" ]; then
        echo -e "${YELLOW}  ⚠ State: unknown${NC}"
    else
        echo -e "${GREEN}  ✓ State: $state${NC}"
    fi
}

# Function to list entities by platform
list_platform() {
    local platform="$1"
    local prefix="${platform}."

    local entities=$(echo "$STATES" | grep -o "\"entity_id\":\"${prefix}melcloud_[^\"]*\"" | cut -d'"' -f4 | sort)
    local count=$(echo "$entities" | grep -c . 2>/dev/null || echo 0)

    if [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}No ${platform} entities found${NC}"
        return
    fi

    local platform_upper=$(echo "$platform" | tr '[:lower:]' '[:upper:]')
    echo -e "${BLUE}═══ ${platform_upper} Platform ($count entities) ═══${NC}"
    echo ""

    for entity in $entities; do
        echo -e "${GREEN}$entity${NC}"
        show_entity "$entity"
        echo ""
    done
}

# Display entities based on platform filter
case "$PLATFORM" in
    climate)
        list_platform "climate"
        ;;
    sensor)
        list_platform "sensor"
        ;;
    binary_sensor)
        list_platform "binary_sensor"
        ;;
    all)
        list_platform "climate"
        list_platform "sensor"
        list_platform "binary_sensor"

        # Summary
        total=$(echo "$STATES" | grep -o '"entity_id":"[^"]*melcloud[^"]*"' | wc -l | xargs)
        echo -e "${BLUE}═══ Summary ═══${NC}"
        echo -e "Total MELCloud entities: ${GREEN}$total${NC}"
        ;;
    *)
        echo -e "${RED}Invalid platform: $PLATFORM${NC}"
        echo "Usage: $0 [climate|sensor|binary_sensor|all]"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}✅ Complete${NC}"
