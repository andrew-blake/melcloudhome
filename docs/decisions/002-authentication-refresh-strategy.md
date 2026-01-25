# ADR-002: Authentication Refresh Strategy

**Date:** 2025-01-17
**Status:** Accepted
**Deciders:** @andrew-blake

## Context

MELCloud Home uses AWS Cognito OAuth with session cookies that expire after ~8 hours. Home Assistant integrations run 24/7, requiring a strategy to handle session expiration without user intervention. The integration must gracefully recover from expired sessions while maintaining security and user experience.

## Decision Drivers

- **User Experience** - No manual re-authentication required during normal operation
- **Uptime** - Integration must work reliably 24/7
- **Session Lifetime** - AWS Cognito sessions expire after ~8 hours
- **Development Speed** - Need working solution for v1.0
- **Security** - Follow OAuth best practices when feasible
- **Incremental Improvement** - Can enhance security posture in future versions

## Options Considered

### Option 1: Automatic Re-login with Stored Credentials (CHOSEN for v1.0)
**Strategy:** Store username/password (encrypted by HA), re-authenticate on 401

**Implementation:**
```python
async def _async_update_data(self):
    try:
        return await self.client.get_devices()
    except AuthenticationError:
        _LOGGER.info("Session expired, re-authenticating...")
        await self.client.login(self._username, self._password)
        return await self.client.get_devices()
```

**Pros:**
- Simple implementation - works immediately
- Transparent to user - no manual intervention
- Home Assistant encrypts credentials in storage
- Suitable for password-based OAuth flow
- Fast to implement for v1.0

**Cons:**
- Stores password long-term (mitigated by HA encryption)
- Extra API call every 8 hours
- Not OAuth best practice (refresh tokens preferred)

### Option 2: HA Re-auth Flow (REJECTED)
**Strategy:** Trigger Home Assistant's re-authentication UI on expiration

**Implementation:**
```python
from homeassistant.exceptions import ConfigEntryAuthFailed

async def _async_update_data(self):
    try:
        return await self.client.get_devices()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed("Session expired") from err
```

**Pros:**
- Standard Home Assistant pattern
- More secure (doesn't store password)
- User explicitly re-authenticates

**Cons:**
- **DEALBREAKER:** Requires user action every 8 hours (3x daily)
- Poor user experience for 24/7 integration
- Defeats purpose of automation
- Not acceptable for production use

**Decision:** Option 2 is NOT acceptable. User experience must not degrade.

### Option 3: OAuth Refresh Tokens (PLANNED for v1.1+)
**Strategy:** Use AWS Cognito refresh tokens for automatic token renewal without re-authentication

**Implementation:**
```python
async def login(self, username: str, password: str) -> dict:
    """Login and return tokens."""
    tokens = {
        "access_token": "...",
        "refresh_token": "...",  # Store this
        "expires_in": 28800,
    }
    return tokens

async def refresh_session(self, refresh_token: str) -> dict:
    """Use refresh token to get new access token."""
    # Call Cognito refresh endpoint
    return new_tokens
```

**Pros:**
- Best security practice - OAuth standard pattern
- No password storage required
- Automatic and transparent
- Industry standard approach
- More maintainable long-term

**Cons:**
- Requires research into Cognito refresh flow
- More implementation complexity
- Additional testing required
- Can defer to v1.1 without impact

## Decision

**v1.0: Option 1 - Automatic Re-login with Stored Credentials**

Implement transparent re-authentication using stored credentials:

```python
# custom_components/melcloudhome/coordinator.py
class MELCloudHomeCoordinator(DataUpdateCoordinator[UserContext]):
    """Manage MELCloud Home data updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="MELCloud Home",
            update_interval=timedelta(seconds=60),
        )
        self.client = MELCloudHomeClient()
        self._username = entry.data["username"]
        self._password = entry.data["password"]  # HA encrypts this
        self._authenticated = False

    async def _async_update_data(self) -> UserContext:
        """Fetch data from API."""
        try:
            if not self._authenticated:
                await self.client.login(self._username, self._password)
                self._authenticated = True

            return await self.client.get_user_context()

        except AuthenticationError:
            # Session expired, re-authenticate transparently
            _LOGGER.info("Session expired, re-authenticating...")
            self._authenticated = False
            await self.client.login(self._username, self._password)
            self._authenticated = True
            return await self.client.get_user_context()
```

**v1.1+: Migrate to Option 3 - OAuth Refresh Tokens**

Future enhancement to implement proper refresh token flow.

## Consequences

### Positive (v1.0)
- **Transparent operation** - Users never see authentication errors
- **Reliable 24/7** - Integration automatically recovers from expiration
- **Fast implementation** - Can ship v1.0 quickly
- **Proven pattern** - Home Assistant encrypts stored credentials
- **Good enough security** - HA's encryption is production-ready

### Negative (v1.0)
- **Suboptimal security** - Storing passwords not OAuth best practice
- **Technical debt** - Will need migration to refresh tokens eventually

### Future Migration (v1.1+)
- Implement AWS Cognito refresh token flow
- Remove password storage requirement
- Enhance security posture
- Align with OAuth 2.0 best practices

### Migration Path

**Phase 1 (v1.0):** Password-based re-authentication
1. Store encrypted credentials in config entry
2. Catch `AuthenticationError` in coordinator
3. Call `client.login()` to establish new session
4. Retry failed operation

**Phase 2 (v1.1+):** Refresh token implementation
1. Research AWS Cognito refresh token endpoint
2. Modify `auth.py` to capture and store refresh token
3. Implement `refresh_session()` method
4. Update coordinator to use refresh flow
5. Migration: Existing users trigger one-time re-auth to capture refresh token

## References

- AWS Cognito OAuth Documentation
- Home Assistant Authentication Best Practices
- `custom_components/melcloudhome/api/client.py:94-95` - Current 401 handling
- Session lifetime: ~8 hours (documented in local development notes)

## Notes

**Why Option 2 is rejected:**
- Requiring user action every 8 hours (3x daily) is unacceptable UX
- Defeats the purpose of home automation
- Would generate user complaints and support burden
- Not a viable production solution

**Why Option 1 now, Option 3 later:**
- Option 1 provides good-enough security with HA's encryption
- Gets v1.0 shipped quickly with reliable operation
- Option 3 is better long-term but requires research and testing
- Incremental improvement is pragmatic approach
- Most users won't notice the difference in security posture

**Security considerations:**
- Home Assistant stores credentials encrypted at rest
- Credentials never leave local network (except to MELCloud API)
- Risk is acceptable for personal home automation use
- Production deployments should migrate to refresh tokens (v1.1)

This decision prioritizes user experience and development speed for v1.0 while maintaining a clear path to enhanced security in v1.1+.
