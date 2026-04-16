# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in Ombra, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. Email **nassimbendaou@users.noreply.github.com** with a detailed description.
3. Include steps to reproduce the vulnerability if possible.
4. You can expect an initial response within **48 hours**.
5. We will work with you to understand and address the issue before any public disclosure.

## Security Practices

- All secrets and API keys are stored in `.env` files excluded from version control.
- No credentials are hardcoded in the source code.
- Backend endpoints use Bearer token authentication.
- Tool execution is governed by a safety layer (`tool_safety.py`).
- Dependencies are regularly reviewed for known vulnerabilities.

## Scope

The following are in scope for security reports:

- Authentication and authorization bypasses
- Injection vulnerabilities (SQL, command, prompt)
- Exposed secrets or credentials
- Remote code execution
- Server-side request forgery (SSRF)

Out of scope:

- Denial of service attacks
- Social engineering
- Issues in third-party dependencies (report these upstream)
