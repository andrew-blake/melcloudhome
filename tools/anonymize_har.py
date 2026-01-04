#!/usr/bin/env python3
"""Anonymize HAR (HTTP Archive) files for MELCloud Home.

Replaces all personally identifiable information with consistent placeholders:
- User details (email, name, IDs)
- Building details (names, IDs)
- Device IDs and MAC addresses
- Authorization tokens
- IP addresses
- Cookies

Usage:
    python tools/anonymize_har.py input.har output_anonymized.har
    python tools/anonymize_har.py input.har  # Auto-generates output name
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, cast


class HARAnonymizer:
    """Anonymizes HAR files while maintaining structure and relationships."""

    def __init__(self):
        """Initialize anonymizer with mapping dictionaries."""
        self.mappings: dict[str, dict[str, str]] = {
            "user_ids": {},
            "building_ids": {},
            "device_ids": {},
            "mac_addresses": {},
            "system_ids": {},
            "emails": {},
            "ip_addresses": {},
        }

        # Counters for generating placeholders
        self.counters: dict[str, int] = {
            "user": 0,
            "building": 0,
            "device": 0,
            "mac": 0,
            "system": 0,
            "email": 0,
            "ip": 0,
        }

    def anonymize_uuid(self, uuid: str, category: str) -> str:
        """Anonymize a UUID while maintaining consistency."""
        mapping_key = f"{category}_ids"

        if uuid in self.mappings[mapping_key]:
            return self.mappings[mapping_key][uuid]

        # Generate placeholder UUID (pattern: AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA)
        letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        letter = letters[self.counters[category] % len(letters)]
        self.counters[category] += 1

        placeholder = (
            f"{letter * 8}-{letter * 4}-{letter * 4}-{letter * 4}-{letter * 12}"
        )
        self.mappings[mapping_key][uuid] = placeholder

        return placeholder

    def anonymize_mac(self, mac: str) -> str:
        """Anonymize MAC address."""
        if mac in self.mappings["mac_addresses"]:
            return self.mappings["mac_addresses"][mac]

        # Generate placeholder MAC
        self.counters["mac"] += 1
        placeholder = f"{self.counters['mac']:012x}"
        self.mappings["mac_addresses"][mac] = placeholder

        return placeholder

    def anonymize_email(self, email: str) -> str:
        """Anonymize email address."""
        if email in self.mappings["emails"]:
            return self.mappings["emails"][email]

        self.counters["email"] += 1
        placeholder = f"user{self.counters['email']}@example.com"
        self.mappings["emails"][email] = placeholder

        return placeholder

    def anonymize_ip(self, ip: str) -> str:
        """Anonymize IP address."""
        if ip in self.mappings["ip_addresses"]:
            return self.mappings["ip_addresses"][ip]

        self.counters["ip"] += 1
        placeholder = f"192.168.1.{self.counters['ip']}"
        self.mappings["ip_addresses"][ip] = placeholder

        return placeholder

    def anonymize_string(self, text: str, field_name: str = "") -> str:
        """Anonymize a string based on patterns and field names."""
        if not isinstance(text, str):
            return text

        # UUID patterns
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

        # Detect category from field name
        field_lower = field_name.lower()
        if "user" in field_lower:
            text = re.sub(
                uuid_pattern,
                lambda m: self.anonymize_uuid(m.group(), "user"),
                text,
                flags=re.IGNORECASE,
            )
        elif "building" in field_lower:
            text = re.sub(
                uuid_pattern,
                lambda m: self.anonymize_uuid(m.group(), "building"),
                text,
                flags=re.IGNORECASE,
            )
        elif "device" in field_lower or "unit" in field_lower:
            text = re.sub(
                uuid_pattern,
                lambda m: self.anonymize_uuid(m.group(), "device"),
                text,
                flags=re.IGNORECASE,
            )
        elif "system" in field_lower:
            text = re.sub(
                uuid_pattern,
                lambda m: self.anonymize_uuid(m.group(), "system"),
                text,
                flags=re.IGNORECASE,
            )
        else:
            # Generic UUID anonymization
            text = re.sub(
                uuid_pattern,
                lambda m: self.anonymize_uuid(m.group(), "device"),
                text,
                flags=re.IGNORECASE,
            )

        # Email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        text = re.sub(email_pattern, lambda m: self.anonymize_email(m.group()), text)

        # IP addresses
        ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        text = re.sub(ip_pattern, lambda m: self.anonymize_ip(m.group()), text)

        # MAC addresses (various formats)
        mac_patterns = [
            r"\b[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\b",
            r"\b[0-9A-Fa-f]{12}\b",
            r"\bFE[0-9A-Fa-f]{30}\b",  # Long format MACs
        ]
        for pattern in mac_patterns:
            text = re.sub(pattern, lambda m: self.anonymize_mac(m.group()), text)

        # Authorization tokens (Bearer tokens, etc.)
        if "bearer" in text.lower():
            text = re.sub(
                r"Bearer\s+[A-Za-z0-9._-]+",
                "Bearer ANONYMIZED_TOKEN",
                text,
                flags=re.IGNORECASE,
            )

        return text

    def anonymize_object(self, obj: Any, path: str = "") -> Any:
        """Recursively anonymize a JSON object."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key

                # Anonymize based on key names
                if key in [
                    "id",
                    "userId",
                    "buildingId",
                    "deviceId",
                    "unitId",
                    "systemId",
                ]:
                    if isinstance(value, str) and re.match(
                        r"[0-9a-f-]{36}", value, re.IGNORECASE
                    ):
                        category = "device"
                        if "user" in key.lower():
                            category = "user"
                        elif "building" in key.lower():
                            category = "building"
                        elif "system" in key.lower():
                            category = "system"
                        result[key] = self.anonymize_uuid(value, category)
                    else:
                        result[key] = value
                elif key in ["email", "Email"]:
                    result[key] = (
                        self.anonymize_email(value) if isinstance(value, str) else value
                    )
                elif key in ["firstname", "lastname", "name", "givenDisplayName"]:
                    # Replace with generic names
                    if key == "firstname":
                        result[key] = "John"
                    elif key == "lastname":
                        result[key] = "Doe"
                    elif key == "givenDisplayName":
                        result[key] = f"Device {self.counters['device']}"
                        self.counters["device"] += 1
                    elif key == "name" and isinstance(value, str):
                        result[key] = f"Building {self.counters['building']}"
                        self.counters["building"] += 1
                    else:
                        result[key] = "Anonymous"
                elif key in ["macAddress", "connectedInterfaceIdentifier"]:
                    result[key] = (
                        self.anonymize_mac(value) if isinstance(value, str) else value
                    )
                elif key in ["authorization", "Authorization", "cookie", "Cookie"]:
                    result[key] = "ANONYMIZED"
                elif isinstance(value, str):
                    result[key] = self.anonymize_string(value, key)
                else:
                    result[key] = self.anonymize_object(value, new_path)

            return result

        elif isinstance(obj, list):
            return [self.anonymize_object(item, f"{path}[]") for item in obj]

        elif isinstance(obj, str):
            return self.anonymize_string(obj, path)

        else:
            return obj

    def anonymize_har(self, har_data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize entire HAR file."""
        print("Anonymizing HAR file...")

        # Anonymize the entire structure
        anonymized = self.anonymize_object(har_data)

        # Print summary
        print("\nAnonymization summary:")
        print(f"  - Users: {len(self.mappings['user_ids'])}")
        print(f"  - Buildings: {len(self.mappings['building_ids'])}")
        print(f"  - Devices: {len(self.mappings['device_ids'])}")
        print(f"  - MAC addresses: {len(self.mappings['mac_addresses'])}")
        print(f"  - System IDs: {len(self.mappings['system_ids'])}")
        print(f"  - Emails: {len(self.mappings['emails'])}")
        print(f"  - IP addresses: {len(self.mappings['ip_addresses'])}")

        # Cast to dict for type checker
        return cast(dict[str, Any], anonymized)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Anonymize HAR files for MELCloud Home",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.har output_anonymized.har
  %(prog)s melcloud_recording.har
  %(prog)s input.har --output docs/research/ATW/recording_anonymized.har
        """,
    )
    parser.add_argument("input", type=str, help="Input HAR file")
    parser.add_argument(
        "output", type=str, nargs="?", help="Output HAR file (optional)"
    )
    parser.add_argument(
        "--output", "-o", dest="output_alt", help="Alternative way to specify output"
    )

    args = parser.parse_args()

    # Determine output file
    if args.output:
        output_file = args.output
    elif args.output_alt:
        output_file = args.output_alt
    else:
        # Auto-generate output filename
        input_path = Path(args.input)
        output_file = str(
            input_path.parent / f"{input_path.stem}_anonymized{input_path.suffix}"
        )

    print(f"Input:  {args.input}")
    print(f"Output: {output_file}")
    print()

    # Load HAR file
    try:
        with open(args.input, encoding="utf-8") as f:
            har_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return 1

    # Anonymize
    anonymizer = HARAnonymizer()
    anonymized_har = anonymizer.anonymize_har(har_data)

    # Save anonymized HAR
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(anonymized_har, f, indent=2)
        print(f"\n✅ Anonymized HAR saved to: {output_file}")
        return 0
    except Exception as e:
        print(f"Error: Failed to write output file: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
