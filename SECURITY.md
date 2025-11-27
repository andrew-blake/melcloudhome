# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | :white_check_mark: |
| < 1.3   | :x:                |

## Reporting a Vulnerability

We take the security of MELCloud Home integration seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **GitHub Security Advisories** (preferred)
   - Go to <https://github.com/andrew-blake/melcloudhome/security/advisories>
   - Click "Report a vulnerability"
   - Provide details about the vulnerability

2. **Email**
   - Send details to: <security@blakenet.uk>
   - Include "SECURITY" in the subject line

### What to Include

Please include the following information in your report:

- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity and complexity

### Disclosure Policy

- We will acknowledge receipt of your vulnerability report within 48 hours
- We will provide a more detailed response within 7 days indicating next steps
- We will keep you informed of the progress towards a fix
- We may ask for additional information or guidance
- We will notify you when the vulnerability is fixed
- We will credit you in the security advisory (unless you prefer to remain anonymous)

### Security Update Process

1. Vulnerability is reported and confirmed
2. Fix is developed and tested
3. New version is released with security patch
4. Security advisory is published
5. Users are notified via GitHub release notes

## Security Best Practices

When using this integration:

1. **Keep Updated**: Always use the latest version available through HACS
2. **Secure Credentials**: Never share your MELCloud credentials or Home Assistant access tokens
3. **Network Security**: Ensure your Home Assistant instance is properly secured
4. **Review Logs**: Check Home Assistant logs regularly for suspicious activity
5. **Report Issues**: If you notice unusual behavior, report it immediately

## Additional Information

- This integration uses cloud polling and does not expose local network services
- All API communication uses HTTPS
- Credentials are stored securely by Home Assistant's credential storage system
- No user data is collected or transmitted beyond what's required for MELCloud API communication

## Questions?

If you have questions about this security policy, please open a [GitHub Discussion](https://github.com/andrew-blake/melcloudhome/discussions).
