#!/bin/bash
# List and inspect MELCloud Home entities via Home Assistant API
#
# LIMITATION: Only finds entities with "melcloud" in the entity_id.
# Old entities from Session 7 (e.g., climate.living_room_a_c) won't be found
# automatically. Check these manually in the HA UI if needed.
#
# Usage: ./tools/list_entities.sh [climate|sensor|binary_sensor|all]

# Load environment
if [ -f .env ]; then
    . .env
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

# Get all states
STATES=$(curl -s -k -X GET "$HA_URL/api/states" \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json")

if [ -z "$STATES" ]; then
    echo -e "${RED}❌ Failed to fetch states from Home Assistant${NC}"
    exit 1
fi

# Function to display entity details
show_entity() {
    local entity_id="$1"

    # Extract state using Python for reliable JSON parsing
    local state=$(echo "$STATES" | python3 -c "
import sys, json
states = json.load(sys.stdin)
for entity in states:
    if entity.get('entity_id') == '${entity_id}':
        print(entity.get('state', 'unknown'))
        break
" 2>/dev/null || echo "error")

    if [ -z "$state" ] || [ "$state" = "error" ]; then
        echo -e "${RED}  ⚠ State: unavailable${NC}"
        return
    fi

    # Color code based on state
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

    # Find entities with "melcloud" in the entity_id
    local entities=$(echo "$STATES" | grep -o "\"entity_id\":\"${prefix}[^\"]*melcloud[^\"]*\"" | cut -d'"' -f4 | sort -u)

    local count=$(echo "$entities" | wc -l | tr -d ' ')

    # If entities is empty, count should be 0
    if [ -z "$entities" ]; then
        count=0
    fi

    if [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}No ${platform} entities found${NC}"
        return
    fi

    local platform_upper=$(echo "$platform" | tr '[:lower:]' '[:upper:]')
    echo -e "${BLUE}═══ ${platform_upper} Platform ($count entities) ═══${NC}"
    echo ""

    echo "$entities" | while read -r entity; do
        if [ -n "$entity" ]; then
            echo -e "${GREEN}$entity${NC}"
            show_entity "$entity"
            echo ""
        fi
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
        total=$(echo "$STATES" | grep -o '"entity_id":"[^"]*melcloud[^"]*"' | wc -l | tr -d ' ')

        echo -e "${BLUE}═══ Summary ═══${NC}"
        echo -e "Total MELCloud entities: ${GREEN}$total${NC}"
        echo -e "${YELLOW}Note: Only includes entities with 'melcloud' in the ID${NC}"
        ;;
    *)
        echo -e "${RED}Invalid platform: $PLATFORM${NC}"
        echo "Usage: $0 [climate|sensor|binary_sensor|all]"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}✅ Complete${NC}"
