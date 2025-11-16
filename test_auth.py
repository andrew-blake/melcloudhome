"""Test authentication module."""

import asyncio
import logging
import os
import sys

# Add custom_components to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "custom_components"))

from melcloudhome.api.auth import MELCloudHomeAuth
from melcloudhome.api.exceptions import AuthenticationError

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def test_auth() -> bool:
    """Test authentication flow."""
    # Get credentials from environment
    username = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    if not username or not password:
        print("ERROR: MELCLOUD_USER and MELCLOUD_PASSWORD must be set in environment")
        print("Example: export MELCLOUD_USER=your@email.com")
        print("         export MELCLOUD_PASSWORD=yourpassword")
        return False

    print(f"\n{'='*60}")
    print("Testing MELCloud Home Authentication")
    print(f"{'='*60}")
    print(f"Username: {username}")
    print(f"{'='*60}\n")

    auth = MELCloudHomeAuth()

    try:
        # Test login
        print("Attempting login...")
        success = await auth.login(username, password)

        if success:
            print("✅ Login successful!")

            # Get session info and debug cookies
            session = await auth.get_session()
            print(f"\nSession: {session}")

            # Debug: Print cookies in jar
            print("\nCookies in jar:")
            for cookie in session.cookie_jar:
                print(
                    f"  {cookie.key}: domain={cookie['domain']}, path={cookie['path']}"
                )

            # Test session check
            print("\nChecking session validity...")
            is_valid = await auth.check_session()
            if is_valid:
                print("✅ Session is valid")
            else:
                print("❌ Session is invalid")
                return False

            # Test logout
            print("\nLogging out...")
            await auth.logout()
            print("✅ Logout successful")

            return True
        else:
            print("❌ Login failed")
            return False

    except AuthenticationError as err:
        print(f"❌ Authentication error: {err}")
        return False
    except Exception as err:
        print(f"❌ Unexpected error: {err}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Ensure cleanup
        await auth.close()


if __name__ == "__main__":
    result = asyncio.run(test_auth())
    sys.exit(0 if result else 1)
