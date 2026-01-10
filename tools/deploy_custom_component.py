#!/usr/bin/env python3
"""Deploy custom component to Home Assistant and verify loading.

Automates the development cycle for custom integrations:
1. Copy component to remote HA instance
2. Restart Home Assistant
3. Monitor logs for successful loading or errors
4. Optionally test via API

Prerequisites:
- SSH access to HA host (configure in .env: HA_SSH_HOST)
- HA API token for testing (optional, in .env: HA_TOKEN)
- Docker container running HA (configure in .env: HA_CONTAINER)

Usage:
    python tools/deploy_custom_component.py [component_name]
    python tools/deploy_custom_component.py melcloudhome --test

Environment (.env):
    HA_SSH_HOST=ha                    # SSH hostname
    HA_CONTAINER=homeassistant        # Docker container name
    HA_URL=http://ha:8123            # Home Assistant URL (for testing)
    HA_TOKEN=your_token_here         # Long-lived access token (for testing)
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

# ANSI colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")


def run_command_with_diagnostics(cmd_list, description="Command"):
    """Run subprocess command with full diagnostic output on failure."""
    result = subprocess.run(cmd_list, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"{RED}❌ {description} failed{NC}")
        print(f"{YELLOW}Command: {' '.join(cmd_list)}{NC}")
        if result.stdout:
            print(f"{YELLOW}Stdout: {result.stdout[:500]}{NC}")
        if result.stderr:
            print(f"{YELLOW}Stderr: {result.stderr[:500]}{NC}")
        print(f"{YELLOW}Return code: {result.returncode}{NC}")

    return result


def run_ssh_command(host, command):
    """Run command on remote host via SSH."""
    result = subprocess.run(
        ["ssh", host, command],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout, result.stderr


def run_ssh_command_with_retry(host, command, retries=2):
    """Run SSH command with retry logic for intermittent failures."""
    for attempt in range(retries):
        # Disable SSH multiplexing to avoid stale socket issues
        result = subprocess.run(
            ["ssh", "-o", "ControlMaster=no", "-o", "ControlPath=none", host, command],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return True, result.stdout, result.stderr

        # On failure, show diagnostics
        if attempt < retries - 1:
            print(
                f"{YELLOW}⚠ SSH command failed (attempt {attempt + 1}/{retries}), retrying...{NC}"
            )
        else:
            print(f"{RED}❌ SSH command failed after {retries} attempts{NC}")
            print(f"{YELLOW}Command: ssh {host} '{command}'{NC}")
            if result.stderr:
                print(f"{YELLOW}Error: {result.stderr[:500]}{NC}")

    return False, result.stdout, result.stderr


def reload_integration(component_name):
    """Reload integration via Home Assistant API."""
    try:
        import requests
    except ImportError:
        return False

    ha_url = os.getenv("HA_URL", "")
    token = os.getenv("HA_TOKEN", "")

    if not ha_url or not token:
        return False

    try:
        headers = {"Authorization": f"Bearer {token}"}

        # Get config entries to find our integration
        response = requests.get(
            f"{ha_url}/api/config/config_entries/entry",
            headers=headers,
            timeout=10,
            verify=False,
        )

        if response.status_code != 200:
            return False

        entries = response.json()
        entry_id = None

        # Find our integration's entry
        for entry in entries:
            if entry.get("domain") == component_name:
                entry_id = entry.get("entry_id")
                break

        if not entry_id:
            print(f"{YELLOW}⚠ Integration not configured yet, using restart{NC}")
            return False

        # Reload the integration
        print(f"{YELLOW}🔄 Reloading integration via API...{NC}")
        response = requests.post(
            f"{ha_url}/api/config/config_entries/entry/{entry_id}/reload",
            headers=headers,
            timeout=30,
            verify=False,
        )

        if response.status_code == 200:
            print(f"{GREEN}✓ Integration reloaded{NC}")
            time.sleep(2)  # Brief wait for reload to complete
            return True
        else:
            print(f"{YELLOW}⚠ Reload failed: {response.status_code}, using restart{NC}")
            return False

    except Exception as e:
        print(f"{YELLOW}⚠ Reload error: {e}, using restart{NC}")
        return False


def deploy_component(
    component_name, ssh_host, container_name, use_reload=False, source_dir="."
):
    """Deploy custom component to Home Assistant.

    Args:
        component_name: Name of the component to deploy
        ssh_host: SSH hostname
        container_name: Docker container name
        use_reload: Use API reload instead of restart
        source_dir: Source directory containing custom_components (default: current directory)
    """
    component_path = Path(source_dir) / "custom_components" / component_name

    if not component_path.exists():
        print(f"{RED}❌ Error: Component not found at {component_path}{NC}")
        return False

    print(f"{BLUE}🚀 Deploying {component_name} to Home Assistant...{NC}\n")

    # Step 1: Copy to remote temp directory
    print(f"{YELLOW}📦 Copying files to {ssh_host}...{NC}")
    success, stdout, stderr = run_ssh_command_with_retry(
        ssh_host, f"mkdir -p /tmp/{component_name}"
    )
    if not success:
        return False  # Error already printed by robust helper

    result = run_command_with_diagnostics(
        [
            "rsync",
            "-az",
            "--delete",
            "-e",
            "ssh -o ControlMaster=no -o ControlPath=none",
            f"{component_path}/",
            f"{ssh_host}:/tmp/{component_name}/",
        ],
        description="Copy files via rsync",
    )
    if result.returncode != 0:
        return False  # Error already printed by diagnostic helper

    print(f"{GREEN}✓ Files copied{NC}")

    # Step 2: Install into HA container
    print(f"{YELLOW}📋 Installing into container...{NC}")
    success, stdout, stderr = run_ssh_command(
        ssh_host,
        f"sudo docker exec {container_name} " f"mkdir -p /config/custom_components",
    )
    if not success:
        print(f"{RED}❌ Failed to create custom_components directory{NC}")
        return False

    success, stdout, stderr = run_ssh_command(
        ssh_host,
        f"sudo docker cp /tmp/{component_name}/. "
        f"{container_name}:/config/custom_components/{component_name}/",
    )
    if not success:
        print(f"{RED}❌ Failed to copy into container{NC}")
        return False

    print(f"{GREEN}✓ Installed into container{NC}")

    # Step 3: Clean up temp directory
    run_ssh_command(ssh_host, f"rm -rf /tmp/{component_name}")

    # Step 4: Restart or Reload Home Assistant
    if use_reload:
        # Try to reload via API first
        if not reload_integration(component_name):
            # Fallback to restart if reload fails
            print(f"{YELLOW}🔄 Restarting Home Assistant (reload failed)...{NC}")
            success, stdout, stderr = run_ssh_command(
                ssh_host, f"sudo docker restart {container_name}"
            )
            if not success:
                print(f"{RED}❌ Failed to restart container{NC}")
                return False
            print(f"{GREEN}✓ Container restarted{NC}")

            # Wait for initialization after restart
            print(f"{YELLOW}⏳ Waiting for Home Assistant to initialize...{NC}")
            time.sleep(5)
            for _attempt in range(30):
                success, stdout, stderr = run_ssh_command(
                    ssh_host, f"sudo docker logs --tail 50 {container_name} 2>&1"
                )
                if success and "Home Assistant initialized" in stdout:
                    print(f"{GREEN}✓ Home Assistant initialized{NC}")
                    break
                time.sleep(2)
            else:
                print(f"{YELLOW}⚠ Timeout waiting for initialization{NC}")
    else:
        # Full restart
        print(f"{YELLOW}🔄 Restarting Home Assistant...{NC}")
        success, stdout, stderr = run_ssh_command(
            ssh_host, f"sudo docker restart {container_name}"
        )
        if not success:
            print(f"{RED}❌ Failed to restart container{NC}")
            return False

        print(f"{GREEN}✓ Container restarted{NC}")

        # Step 5: Wait for initialization
        print(f"{YELLOW}⏳ Waiting for Home Assistant to initialize...{NC}")
        time.sleep(5)

        for _attempt in range(30):
            success, stdout, stderr = run_ssh_command(
                ssh_host, f"sudo docker logs --tail 50 {container_name} 2>&1"
            )
            if success and "Home Assistant initialized" in stdout:
                print(f"{GREEN}✓ Home Assistant initialized{NC}")
                break
            time.sleep(2)
        else:
            print(
                f"{YELLOW}⚠ Timeout waiting for initialization (may still be starting){NC}"
            )

    # Step 6: Check for integration loading
    print(f"\n{BLUE}🔍 Checking integration logs...{NC}")
    success, stdout, _stderr = run_ssh_command(
        ssh_host, f"sudo docker logs --tail 500 {container_name} 2>&1"
    )

    if success:
        component_logs = [
            line
            for line in stdout.split("\n")
            if f"custom_components.{component_name}" in line
        ]

        if component_logs:
            print(f"{GREEN}✓ Integration detected in logs{NC}")
            print(f"\n{BLUE}📋 Recent integration logs:{NC}")
            for line in component_logs[-10:]:
                print(f"   {line}")

            # Check for errors
            error_logs = [
                line
                for line in component_logs
                if any(
                    word in line.lower()
                    for word in ["error", "exception", "traceback", "failed"]
                )
            ]
            if error_logs:
                print(f"\n{RED}❌ ERRORS DETECTED:{NC}")
                for line in error_logs[-10:]:
                    print(f"   {line}")
                return False
        else:
            print(f"{YELLOW}⚠ Integration not found in recent logs{NC}")

    print(f"\n{GREEN}✅ Deployment complete!{NC}")
    return True


def test_integration(component_name):
    """Test integration via Home Assistant API."""
    try:
        import requests
    except ImportError:
        print(f"{YELLOW}⚠ requests library not available, skipping API tests{NC}")
        return

    ha_url = os.getenv("HA_URL", "")
    token = os.getenv("HA_TOKEN", "")

    if not ha_url or not token:
        print(f"{YELLOW}⚠ HA_URL or HA_TOKEN not set, skipping API tests{NC}")
        print("   Set these in .env to enable API testing")
        return

    print(f"\n{BLUE}🧪 Testing integration via API...{NC}")

    try:
        headers = {"Authorization": f"Bearer {token}"}

        # Test 1: Get all states and find component entities
        response = requests.get(f"{ha_url}/api/states", headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"{RED}❌ API connection failed{NC}")
            return

        states = response.json()
        component_entities = [
            s
            for s in states
            if s.get("attributes", {})
            .get("attribution", "")
            .lower()
            .find(component_name.replace("_", " "))
            != -1
            or s.get("entity_id", "").startswith("climate.")  # Adjust domain as needed
        ]

        if component_entities:
            print(f"{GREEN}✓ Found {len(component_entities)} entity(s){NC}")
            for entity in component_entities[:5]:  # Show first 5
                entity_id = entity["entity_id"]
                state = entity["state"]
                print(f"   • {entity_id}: {state}")
        else:
            print(f"{YELLOW}⚠ No entities found (may need configuration){NC}")

    except Exception as e:
        print(f"{RED}❌ API test error: {e}{NC}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deploy custom component to Home Assistant"
    )
    parser.add_argument(
        "component",
        nargs="?",
        default="melcloudhome",
        help="Component name (default: melcloudhome)",
    )
    parser.add_argument(
        "--test", action="store_true", help="Run API tests after deploy"
    )
    parser.add_argument("--watch", action="store_true", help="Watch logs after deploy")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reload integration via API instead of full restart (faster)",
    )
    parser.add_argument(
        "--source-dir",
        default=".",
        help="Source directory containing custom_components (default: current directory)",
    )

    args = parser.parse_args()

    # Load environment
    load_env_file()

    ssh_host = os.getenv("HA_SSH_HOST", "ha")
    container = os.getenv("HA_CONTAINER", "homeassistant")

    # Validate source directory
    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"{RED}❌ Error: Source directory not found: {source_dir}{NC}")
        sys.exit(1)

    # Deploy
    success = deploy_component(
        args.component, ssh_host, container, args.reload, str(source_dir)
    )

    if not success:
        sys.exit(1)

    # Optional: Test via API
    if args.test:
        test_integration(args.component)

    # Optional: Watch logs
    if args.watch:
        print(f"\n{BLUE}👀 Watching logs (Ctrl+C to exit)...{NC}")
        subprocess.run(
            [
                "ssh",
                ssh_host,
                f"sudo docker logs -f --tail 50 {container} 2>&1 | grep {args.component}",
            ]
        )

    print(f"\n{BLUE}Next steps:{NC}")
    print(f"1. Open Home Assistant UI: {os.getenv('HA_URL', 'http://ha:8123')}")
    print("2. Configuration → Integrations → Add Integration")
    print(f"3. Search for '{args.component}' and configure")


if __name__ == "__main__":
    main()
