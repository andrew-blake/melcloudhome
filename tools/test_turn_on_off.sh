#!/bin/bash
# Test script for v1.1.3 turn_on/turn_off functionality
# Usage: ./tools/test_turn_on_off.sh

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

echo "🔍 Finding MELCloud climate entities..."

# Get all climate entities
ENTITIES=$(curl -s -k -X GET "$HA_URL/api/states" \
    -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json" | \
    grep -o '"entity_id":"climate\.melcloud_[^"]*"' | \
    cut -d'"' -f4)

if [ -z "$ENTITIES" ]; then
    echo "❌ No MELCloud climate entities found"
    exit 1
fi

echo "✅ Found entities:"
echo "$ENTITIES"

# Test each entity
for ENTITY in $ENTITIES; do
    echo ""
    echo "Testing $ENTITY..."

    # Get current state
    STATE=$(curl -s -k -X GET "$HA_URL/api/states/$ENTITY" \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json")

    # Check supported_features
    FEATURES=$(echo "$STATE" | grep -o '"supported_features":[0-9]*' | cut -d':' -f2)
    echo "  Supported Features: $FEATURES"

    # Check if TURN_ON (256) and TURN_OFF (128) are included
    if [ $((FEATURES & 256)) -eq 256 ] && [ $((FEATURES & 128)) -eq 128 ]; then
        echo "  ✅ TURN_ON and TURN_OFF features are supported"
    else
        echo "  ❌ Missing TURN_ON or TURN_OFF features"
    fi

    # Test turn_off
    echo "  Testing climate.turn_off..."
    curl -s -k -X POST "$HA_URL/api/services/climate/turn_off" \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"entity_id\": \"$ENTITY\"}" > /dev/null

    sleep 2

    # Check state is off
    NEW_STATE=$(curl -s -k -X GET "$HA_URL/api/states/$ENTITY" \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json" | grep -o '"state":"[^"]*"' | cut -d'"' -f4)

    if [ "$NEW_STATE" = "off" ]; then
        echo "  ✅ Successfully turned off"
    else
        echo "  ❌ Failed to turn off (state: $NEW_STATE)"
    fi

    # Test turn_on
    echo "  Testing climate.turn_on..."
    curl -s -k -X POST "$HA_URL/api/services/climate/turn_on" \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"entity_id\": \"$ENTITY\"}" > /dev/null

    sleep 2

    # Check state is not off
    NEW_STATE=$(curl -s -k -X GET "$HA_URL/api/states/$ENTITY" \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json" | grep -o '"state":"[^"]*"' | cut -d'"' -f4)

    if [ "$NEW_STATE" != "off" ]; then
        echo "  ✅ Successfully turned on (state: $NEW_STATE)"
    else
        echo "  ❌ Failed to turn on"
    fi
done

echo ""
echo "✅ Testing complete!"
