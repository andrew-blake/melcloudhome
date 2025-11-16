import os

import requests
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load from environment
HA_URL = "https://homeassistant.local:8123"
HA_TOKEN = os.getenv("HA_API_KEY")

headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}

sensors = [
    "binary_sensor.octopus_energy_00000000_0009_4000_8020_00000001202e_intelligent_dispatching",
    "sensor.myenergi_zappi_22217206_plug_status",
    "sensor.myenergi_zappi_22217206_status",
    "sensor.intelligent_octopus_go_smart_charging_session",
]

for sensor in sensors:
    try:
        response = requests.get(
            f"{HA_URL}/api/states/{sensor}", headers=headers, verify=False
        )
        if response.status_code == 200:
            data = response.json()
            print(f"\n{sensor}:")
            print(f"  State: {data['state']}")
            print(f"  Last Updated: {data.get('last_updated', 'N/A')}")
            if data.get("attributes"):
                print("  Attributes:")
                for key, val in data["attributes"].items():
                    if key not in ["icon", "device_class"]:
                        print(f"    {key}: {val}")
        else:
            print(f"\n{sensor}: HTTP {response.status_code}")
    except Exception as e:
        print(f"\n{sensor}: Error - {e}")
