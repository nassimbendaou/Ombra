# Skill: Code Review

## Purpose
Expert code review for any language. Identify bugs, security issues, performance problems, and style violations.

## When to Activate
Activate this skill when the user asks to review, audit, or improve code.

## Instructions

When reviewing code:
1. **Security first** — Check for injection vulnerabilities, hardcoded secrets, unsafe deserialization
2. **Correctness** — Logic errors, off-by-one, null pointer risks
3. **Performance** — O(n²) where O(n) works, unnecessary allocations, blocking I/O
4. **Maintainability** — Function length, naming, coupling
5. **Style** — Consistency with language idioms

Output format:
- **Critical** (must fix): security or crash bugs
- **Warning** (should fix): logic or performance issues
- **Suggestion** (nice to have): style and readability

Be specific: quote the problematic line, explain why, show the fix.
