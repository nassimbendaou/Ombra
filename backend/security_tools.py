"""
Ombra Security Center — Blue Team Operations Module
Real-time network scanning, vulnerability assessment, log analysis,
threat intelligence, and hardening recommendations.
"""

import os
import re
import json
import asyncio
import subprocess
import socket
import ssl
import hashlib
import platform
import ipaddress
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# ── Port Scanner ─────────────────────────────────────────────────────────────

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 111: "RPCbind", 135: "MSRPC", 139: "NetBIOS",
    143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS", 995: "POP3S",
    1433: "MSSQL", 1521: "Oracle", 3306: "MySQL", 3389: "RDP",
    5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Proxy",
    8443: "HTTPS-Alt", 8888: "HTTP-Alt", 9200: "Elasticsearch",
    27017: "MongoDB", 6443: "K8s-API"
}

DANGEROUS_PORTS = {23, 21, 135, 139, 445, 111, 6379, 9200, 27017, 5900}


async def scan_port(host: str, port: int, timeout: float = 2.0) -> dict:
    """Scan a single port on a host."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        service = COMMON_PORTS.get(port, "unknown")
        return {
            "port": port, "state": "open", "service": service,
            "risk": "high" if port in DANGEROUS_PORTS else "medium" if service == "unknown" else "low"
        }
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return {"port": port, "state": "closed"}


async def scan_ports(host: str, ports: List[int] = None, timeout: float = 2.0) -> dict:
    """Scan multiple ports on a host concurrently."""
    if ports is None:
        ports = list(COMMON_PORTS.keys())
    
    # Validate host — only IPs and hostnames, no command injection
    if not re.match(r'^[a-zA-Z0-9\.\-]+$', host):
        return {"error": "Invalid host format"}
    
    start = datetime.now(timezone.utc)
    tasks = [scan_port(host, p, timeout) for p in ports]
    results = await asyncio.gather(*tasks)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    
    open_ports = [r for r in results if r["state"] == "open"]
    high_risk = [r for r in open_ports if r.get("risk") == "high"]
    
    return {
        "host": host,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "ports_scanned": len(ports),
        "open_ports": open_ports,
        "summary": {
            "total_open": len(open_ports),
            "high_risk": len(high_risk),
            "services": [f"{r['port']}/{r['service']}" for r in open_ports]
        },
        "risk_level": "critical" if len(high_risk) > 2 else "high" if high_risk else "medium" if len(open_ports) > 5 else "low"
    }


# ── SSL/TLS Certificate Checker ─────────────────────────────────────────────

async def check_ssl(host: str, port: int = 443) -> dict:
    """Check SSL/TLS certificate details and security."""
    if not re.match(r'^[a-zA-Z0-9\.\-]+$', host):
        return {"error": "Invalid host format"}
    
    try:
        ctx = ssl.create_default_context()
        loop = asyncio.get_event_loop()
        
        def _check():
            with socket.create_connection((host, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    return cert, cipher, version
        
        cert, cipher, version = await loop.run_in_executor(None, _check)
        
        # Parse cert dates
        not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
        not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
        days_left = (not_after - datetime.utcnow()).days
        
        # Extract SANs
        sans = []
        for type_, value in cert.get('subjectAltName', []):
            sans.append(value)
        
        # Assess issues
        issues = []
        if days_left < 0:
            issues.append({"severity": "critical", "message": "Certificate EXPIRED"})
        elif days_left < 30:
            issues.append({"severity": "high", "message": f"Certificate expires in {days_left} days"})
        elif days_left < 90:
            issues.append({"severity": "medium", "message": f"Certificate expires in {days_left} days"})
        
        if version in ("TLSv1", "TLSv1.1", "SSLv3"):
            issues.append({"severity": "high", "message": f"Insecure protocol: {version}"})
        
        weak_ciphers = ["RC4", "DES", "3DES", "MD5"]
        if cipher and any(w in cipher[0].upper() for w in weak_ciphers):
            issues.append({"severity": "high", "message": f"Weak cipher: {cipher[0]}"})
        
        return {
            "host": host,
            "port": port,
            "valid": days_left >= 0,
            "issuer": dict(x[0] for x in cert.get('issuer', [])),
            "subject": dict(x[0] for x in cert.get('subject', [])),
            "not_before": not_before.isoformat(),
            "not_after": not_after.isoformat(),
            "days_remaining": days_left,
            "protocol": version,
            "cipher": cipher[0] if cipher else None,
            "sans": sans[:20],
            "issues": issues,
            "risk_level": "critical" if any(i["severity"] == "critical" for i in issues) else
                         "high" if any(i["severity"] == "high" for i in issues) else
                         "medium" if issues else "low"
        }
    except Exception as e:
        return {"host": host, "port": port, "error": str(e), "risk_level": "unknown"}


# ── System Hardening Audit ───────────────────────────────────────────────────

async def audit_system() -> dict:
    """Audit the local system for security hardening issues."""
    findings = []
    
    async def _run(cmd: str) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return stdout.decode().strip()
        except Exception:
            return ""
    
    is_linux = platform.system() == "Linux"
    
    if is_linux:
        # Check SSH config
        ssh_config = await _run("cat /etc/ssh/sshd_config 2>/dev/null")
        if ssh_config:
            if re.search(r'PermitRootLogin\s+yes', ssh_config):
                findings.append({"category": "SSH", "severity": "critical",
                    "finding": "Root login enabled via SSH",
                    "remediation": "Set 'PermitRootLogin no' in /etc/ssh/sshd_config"})
            if re.search(r'PasswordAuthentication\s+yes', ssh_config):
                findings.append({"category": "SSH", "severity": "high",
                    "finding": "Password authentication enabled (prefer key-based auth)",
                    "remediation": "Set 'PasswordAuthentication no' in /etc/ssh/sshd_config"})
            if not re.search(r'Protocol\s+2', ssh_config) and 'Protocol' in ssh_config:
                findings.append({"category": "SSH", "severity": "high",
                    "finding": "SSH Protocol 1 may be enabled",
                    "remediation": "Set 'Protocol 2' in /etc/ssh/sshd_config"})
        
        # Check firewall
        ufw = await _run("ufw status 2>/dev/null")
        iptables = await _run("iptables -L -n 2>/dev/null | head -20")
        if "inactive" in ufw.lower() and (not iptables or "ACCEPT" not in iptables):
            findings.append({"category": "Firewall", "severity": "critical",
                "finding": "No active firewall detected",
                "remediation": "Enable ufw: sudo ufw enable"})
        
        # Check unattended upgrades
        auto_upgrades = await _run("cat /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null")
        if not auto_upgrades or "1" not in auto_upgrades:
            findings.append({"category": "Updates", "severity": "medium",
                "finding": "Automatic security updates not configured",
                "remediation": "sudo apt install unattended-upgrades && sudo dpkg-reconfigure unattended-upgrades"})
        
        # Check fail2ban
        f2b = await _run("systemctl is-active fail2ban 2>/dev/null")
        if f2b != "active":
            findings.append({"category": "Intrusion Prevention", "severity": "high",
                "finding": "fail2ban not running",
                "remediation": "sudo apt install fail2ban && sudo systemctl enable fail2ban --now"})
        
        # Check for SUID binaries
        suid = await _run("find /usr/bin /usr/sbin -perm -4000 -type f 2>/dev/null | head -30")
        suspicious_suid = [b for b in suid.split('\n') if b and any(s in b for s in ['nmap', 'wget', 'curl', 'python', 'perl', 'ruby', 'bash', 'nc', 'vim'])]
        if suspicious_suid:
            findings.append({"category": "Privileges", "severity": "high",
                "finding": f"Suspicious SUID binaries: {', '.join(suspicious_suid)}",
                "remediation": "Remove SUID bit: sudo chmod u-s <binary>"})
        
        # Check world-writable directories
        world_writable = await _run("find / -maxdepth 3 -type d -perm -002 ! -path '/proc/*' ! -path '/sys/*' ! -path '/tmp' ! -path '/var/tmp' 2>/dev/null | head -10")
        if world_writable:
            dirs = [d for d in world_writable.split('\n') if d]
            if dirs:
                findings.append({"category": "Filesystem", "severity": "medium",
                    "finding": f"World-writable directories: {', '.join(dirs[:5])}",
                    "remediation": "chmod o-w on affected directories"})
        
        # Check open listening ports
        listening = await _run("ss -tlnp 2>/dev/null | tail -n +2")
        if listening:
            exposed = []
            for line in listening.split('\n'):
                if '0.0.0.0:' in line or ':::' in line:
                    match = re.search(r'(?:0\.0\.0\.0|:::):(\d+)', line)
                    if match:
                        port = int(match.group(1))
                        if port in DANGEROUS_PORTS:
                            exposed.append(port)
            if exposed:
                findings.append({"category": "Network", "severity": "high",
                    "finding": f"Dangerous services exposed on all interfaces: {exposed}",
                    "remediation": "Bind services to 127.0.0.1 or use firewall rules"})
        
        # Check .env files permissions
        env_files = await _run("find /home -name '.env' -type f 2>/dev/null | head -10")
        for ef in env_files.split('\n'):
            if ef:
                perms = await _run(f"stat -c '%a' {ef} 2>/dev/null")
                if perms and int(perms) > 600:
                    findings.append({"category": "Secrets", "severity": "high",
                        "finding": f"{ef} has overly permissive mode {perms}",
                        "remediation": f"chmod 600 {ef}"})
    
    # Score
    crit = sum(1 for f in findings if f["severity"] == "critical")
    high = sum(1 for f in findings if f["severity"] == "high")
    med = sum(1 for f in findings if f["severity"] == "medium")
    
    max_score = 100
    score = max(0, max_score - (crit * 25) - (high * 10) - (med * 5))
    
    return {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "hostname": platform.node(),
        "findings": findings,
        "summary": {
            "total": len(findings),
            "critical": crit,
            "high": high,
            "medium": med,
            "score": score,
            "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
        }
    }


# ── Log Analysis (SIEM-lite) ────────────────────────────────────────────────

SUSPICIOUS_PATTERNS = [
    {"pattern": r"Failed password for .+ from ([\d\.]+)", "type": "brute_force", "severity": "high"},
    {"pattern": r"Invalid user (\w+) from ([\d\.]+)", "type": "user_enum", "severity": "medium"},
    {"pattern": r"Connection closed by ([\d\.]+) .+\[preauth\]", "type": "ssh_probe", "severity": "medium"},
    {"pattern": r"reverse mapping checking .+ POSSIBLE BREAK-IN", "type": "dns_spoof", "severity": "high"},
    {"pattern": r"segfault at", "type": "crash", "severity": "medium"},
    {"pattern": r"SYN flooding on port", "type": "dos", "severity": "critical"},
    {"pattern": r"Out of memory: Kill process", "type": "oom_kill", "severity": "high"},
    {"pattern": r"COMMAND=.+(?:chmod|chown|useradd|passwd|visudo)", "type": "priv_escalation", "severity": "high"},
    {"pattern": r"Accepted publickey for .+ from ([\d\.]+)", "type": "auth_success", "severity": "info"},
    {"pattern": r"session opened for user root", "type": "root_session", "severity": "medium"},
]


async def analyze_logs(log_paths: List[str] = None, lines: int = 2000) -> dict:
    """Analyze system logs for security events."""
    if log_paths is None:
        log_paths = [
            "/var/log/auth.log", "/var/log/syslog", "/var/log/kern.log",
            "/var/log/nginx/access.log", "/var/log/nginx/error.log",
            "/var/log/ombra-backend.err.log"
        ]
    
    events = []
    ip_counter: Dict[str, int] = {}
    
    for log_path in log_paths:
        if not os.path.exists(log_path):
            continue
        try:
            proc = await asyncio.create_subprocess_exec(
                "tail", "-n", str(lines), log_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            content = stdout.decode(errors='replace')
        except Exception:
            continue
        
        for line in content.split('\n'):
            if not line.strip():
                continue
            for sp in SUSPICIOUS_PATTERNS:
                m = re.search(sp["pattern"], line)
                if m:
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    ip = ip_match.group(1) if ip_match else None
                    if ip:
                        ip_counter[ip] = ip_counter.get(ip, 0) + 1
                    
                    events.append({
                        "type": sp["type"],
                        "severity": sp["severity"],
                        "source": os.path.basename(log_path),
                        "ip": ip,
                        "line": line[:300],
                        "timestamp": _extract_timestamp(line)
                    })
                    break
    
    # Identify top attackers
    top_ips = sorted(ip_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Detect brute force (>10 failures from same IP)
    brute_force_ips = [ip for ip, count in ip_counter.items() if count >= 10]
    
    alerts = []
    if brute_force_ips:
        alerts.append({
            "type": "brute_force_detected",
            "severity": "critical",
            "message": f"Active brute force from {len(brute_force_ips)} IP(s): {', '.join(brute_force_ips[:5])}",
            "action": f"sudo ufw deny from {brute_force_ips[0]}"
        })
    
    crit_events = [e for e in events if e["severity"] == "critical"]
    if crit_events:
        alerts.append({
            "type": "critical_events",
            "severity": "critical",
            "message": f"{len(crit_events)} critical security events detected",
            "action": "Review events immediately"
        })
    
    return {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "logs_analyzed": len([p for p in log_paths if os.path.exists(p)]),
        "events": events[-100:],  # Last 100 events
        "alerts": alerts,
        "top_ips": [{"ip": ip, "hits": count, "threat": "high" if count >= 10 else "medium"} for ip, count in top_ips],
        "summary": {
            "total_events": len(events),
            "critical": sum(1 for e in events if e["severity"] == "critical"),
            "high": sum(1 for e in events if e["severity"] == "high"),
            "medium": sum(1 for e in events if e["severity"] == "medium"),
            "brute_force_ips": len(brute_force_ips),
            "unique_ips": len(ip_counter)
        }
    }


def _extract_timestamp(line: str) -> Optional[str]:
    """Try to extract a timestamp from a log line."""
    patterns = [
        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})',  # ISO
        r'([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',  # syslog
    ]
    for p in patterns:
        m = re.search(p, line)
        if m:
            return m.group(1)
    return None


# ── Network Reconnaissance ───────────────────────────────────────────────────

async def check_dns(domain: str) -> dict:
    """Check DNS records for a domain."""
    if not re.match(r'^[a-zA-Z0-9\.\-]+$', domain):
        return {"error": "Invalid domain format"}
    
    results = {}
    record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
    
    for rtype in record_types:
        try:
            proc = await asyncio.create_subprocess_exec(
                "dig", "+short", domain, rtype,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            output = stdout.decode().strip()
            if output:
                results[rtype] = output.split('\n')
        except Exception:
            continue
    
    # Security checks
    issues = []
    txt_records = results.get("TXT", [])
    has_spf = any("v=spf1" in t for t in txt_records)
    has_dmarc = False
    has_dkim = False
    
    # Check DMARC
    try:
        proc = await asyncio.create_subprocess_exec(
            "dig", "+short", f"_dmarc.{domain}", "TXT",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if stdout.decode().strip():
            has_dmarc = True
            results["DMARC"] = [stdout.decode().strip()]
    except Exception:
        pass
    
    if not has_spf:
        issues.append({"severity": "high", "message": "No SPF record — vulnerable to email spoofing"})
    if not has_dmarc:
        issues.append({"severity": "high", "message": "No DMARC record — email authentication incomplete"})
    
    return {
        "domain": domain,
        "records": results,
        "email_security": {
            "spf": has_spf, "dmarc": has_dmarc, "dkim": has_dkim
        },
        "issues": issues
    }


# ── HTTP Security Headers Checker ────────────────────────────────────────────

REQUIRED_HEADERS = {
    "Strict-Transport-Security": {"severity": "high", "desc": "HSTS not set — vulnerable to protocol downgrade"},
    "X-Content-Type-Options": {"severity": "medium", "desc": "Missing — MIME type sniffing possible"},
    "X-Frame-Options": {"severity": "medium", "desc": "Missing — clickjacking possible"},
    "Content-Security-Policy": {"severity": "high", "desc": "No CSP — XSS risk elevated"},
    "X-XSS-Protection": {"severity": "low", "desc": "Missing legacy XSS protection header"},
    "Referrer-Policy": {"severity": "low", "desc": "Missing — referrer leakage possible"},
    "Permissions-Policy": {"severity": "low", "desc": "Missing — browser features not restricted"},
}

DANGEROUS_HEADERS = ["Server", "X-Powered-By", "X-AspNet-Version"]


async def check_http_headers(url: str) -> dict:
    """Analyze HTTP security headers of a URL."""
    import httpx
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10, verify=False) as client:
            resp = await client.get(url)
            headers = dict(resp.headers)
    except Exception as e:
        return {"error": str(e)}
    
    missing = []
    present = []
    info_leaked = []
    
    for header, meta in REQUIRED_HEADERS.items():
        if header.lower() in {k.lower() for k in headers}:
            val = next(v for k, v in headers.items() if k.lower() == header.lower())
            present.append({"header": header, "value": val[:200]})
        else:
            missing.append({"header": header, "severity": meta["severity"], "description": meta["desc"]})
    
    for header in DANGEROUS_HEADERS:
        if header.lower() in {k.lower() for k in headers}:
            val = next(v for k, v in headers.items() if k.lower() == header.lower())
            info_leaked.append({"header": header, "value": val, "severity": "medium",
                                "description": f"Server info leaked: {val}"})
    
    total_checks = len(REQUIRED_HEADERS)
    passed = total_checks - len(missing)
    score = round((passed / total_checks) * 100)
    
    return {
        "url": url,
        "status_code": resp.status_code,
        "present_headers": present,
        "missing_headers": missing,
        "info_leaked": info_leaked,
        "score": score,
        "grade": "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 30 else "F"
    }


# ── File Integrity Monitor ──────────────────────────────────────────────────

async def compute_file_hashes(paths: List[str]) -> dict:
    """Compute SHA-256 hashes for files to detect tampering."""
    results = []
    for p in paths:
        if not os.path.isfile(p):
            results.append({"path": p, "error": "File not found"})
            continue
        try:
            h = hashlib.sha256()
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            stat = os.stat(p)
            results.append({
                "path": p,
                "sha256": h.hexdigest(),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "permissions": oct(stat.st_mode)[-3:]
            })
        except Exception as e:
            results.append({"path": p, "error": str(e)})
    
    return {"files": results, "computed_at": datetime.now(timezone.utc).isoformat()}


async def check_file_integrity(baseline: dict, current: dict) -> dict:
    """Compare file hashes against a baseline to detect changes."""
    baseline_map = {f["path"]: f for f in baseline.get("files", []) if "sha256" in f}
    current_map = {f["path"]: f for f in current.get("files", []) if "sha256" in f}
    
    modified = []
    removed = []
    added = []
    
    for path, bl in baseline_map.items():
        if path not in current_map:
            removed.append({"path": path, "severity": "high"})
        elif current_map[path]["sha256"] != bl["sha256"]:
            modified.append({
                "path": path,
                "old_hash": bl["sha256"][:16] + "...",
                "new_hash": current_map[path]["sha256"][:16] + "...",
                "severity": "high"
            })
    
    for path in current_map:
        if path not in baseline_map:
            added.append({"path": path, "severity": "medium"})
    
    return {
        "check_time": datetime.now(timezone.utc).isoformat(),
        "modified": modified,
        "removed": removed,
        "added": added,
        "total_changes": len(modified) + len(removed) + len(added),
        "integrity": "compromised" if modified or removed else "clean"
    }


# ── Dependency Vulnerability Scanner ─────────────────────────────────────────

async def scan_dependencies(project_path: str) -> dict:
    """Scan Python/Node dependencies for known vulnerabilities."""
    results = {"python": None, "node": None, "scan_time": datetime.now(timezone.utc).isoformat()}
    
    # Python — pip audit
    req_file = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_file):
        try:
            proc = await asyncio.create_subprocess_exec(
                "pip", "audit", "-r", req_file, "--format", "json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if stdout:
                results["python"] = json.loads(stdout.decode())
            else:
                # Try pip-audit as module
                proc2 = await asyncio.create_subprocess_exec(
                    "python3", "-m", "pip_audit", "-r", req_file, "--format", "json",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=30)
                if stdout2:
                    results["python"] = json.loads(stdout2.decode())
        except Exception as e:
            results["python"] = {"error": str(e)}
    
    # Node — npm audit
    pkg_file = os.path.join(project_path, "package.json")
    if os.path.exists(pkg_file):
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "audit", "--json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=project_path
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if stdout:
                results["node"] = json.loads(stdout.decode())
        except Exception as e:
            results["node"] = {"error": str(e)}
    
    return results


# ── Threat Intelligence Lookup ───────────────────────────────────────────────

async def lookup_ip_reputation(ip: str) -> dict:
    """Check IP reputation using AbuseIPDB-style heuristics + local data."""
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
        return {"error": "Invalid IP format"}
    
    import httpx
    
    result = {
        "ip": ip,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": []
    }
    
    # Check local auth.log for this IP
    local_hits = 0
    try:
        proc = await asyncio.create_subprocess_exec(
            "grep", "-c", ip, "/var/log/auth.log",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        local_hits = int(stdout.decode().strip() or 0)
    except Exception:
        pass
    
    result["local_hits"] = local_hits
    if local_hits > 20:
        result["sources"].append({"source": "local_logs", "verdict": "malicious", "hits": local_hits})
    elif local_hits > 5:
        result["sources"].append({"source": "local_logs", "verdict": "suspicious", "hits": local_hits})
    
    # ipinfo.io (free, no key needed)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://ipinfo.io/{ip}/json")
            if resp.status_code == 200:
                data = resp.json()
                result["geo"] = {
                    "country": data.get("country"),
                    "region": data.get("region"),
                    "city": data.get("city"),
                    "org": data.get("org"),
                    "hostname": data.get("hostname")
                }
    except Exception:
        pass
    
    # Reverse DNS
    try:
        loop = asyncio.get_event_loop()
        hostname = await loop.run_in_executor(None, lambda: socket.gethostbyaddr(ip))
        result["reverse_dns"] = hostname[0]
    except Exception:
        result["reverse_dns"] = None
    
    # Risk assessment
    risk_score = 0
    if local_hits > 20:
        risk_score += 50
    elif local_hits > 5:
        risk_score += 25
    
    result["risk_score"] = min(100, risk_score)
    result["verdict"] = "malicious" if risk_score >= 50 else "suspicious" if risk_score >= 25 else "clean"
    
    return result


# ── WHOIS Lookup ─────────────────────────────────────────────────────────────

async def whois_lookup(target: str) -> dict:
    """WHOIS lookup for a domain or IP address."""
    import httpx

    result = {"target": target, "checked_at": datetime.now(timezone.utc).isoformat()}

    # Try system whois command first
    try:
        proc = await asyncio.create_subprocess_exec(
            "whois", target,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        raw = stdout.decode(errors="replace")
        result["raw"] = raw[:5000]

        # Parse key fields
        parsed = {}
        field_map = {
            "Registrar:": "registrar",
            "Creation Date:": "created",
            "Updated Date:": "updated",
            "Registry Expiry Date:": "expires",
            "Registrant Organization:": "organization",
            "Registrant Country:": "country",
            "Name Server:": "nameservers",
            "DNSSEC:": "dnssec",
            "Registrant Email:": "email",
            "Admin Email:": "admin_email",
            "Registrar URL:": "registrar_url",
        }
        nameservers = []
        for line in raw.splitlines():
            line = line.strip()
            for prefix, key in field_map.items():
                if line.startswith(prefix):
                    val = line[len(prefix):].strip()
                    if key == "nameservers":
                        nameservers.append(val.lower())
                    else:
                        parsed[key] = val
        if nameservers:
            parsed["nameservers"] = list(set(nameservers))
        result["parsed"] = parsed
    except FileNotFoundError:
        # Fallback: use RDAP via httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', target):
                    resp = await client.get(f"https://rdap.org/ip/{target}")
                else:
                    resp = await client.get(f"https://rdap.org/domain/{target}")
                if resp.status_code == 200:
                    data = resp.json()
                    result["rdap"] = {
                        "name": data.get("name") or data.get("ldhName"),
                        "handle": data.get("handle"),
                        "status": data.get("status"),
                        "events": [
                            {"action": e["eventAction"], "date": e["eventDate"]}
                            for e in data.get("events", [])
                        ],
                        "nameservers": [
                            ns.get("ldhName") for ns in data.get("nameservers", [])
                        ] if "nameservers" in data else None,
                    }
                    result["parsed"] = {
                        "status": ", ".join(data.get("status", [])),
                    }
                    for e in data.get("events", []):
                        if e["eventAction"] == "registration":
                            result["parsed"]["created"] = e["eventDate"]
                        elif e["eventAction"] == "expiration":
                            result["parsed"]["expires"] = e["eventDate"]
                        elif e["eventAction"] == "last changed":
                            result["parsed"]["updated"] = e["eventDate"]
        except Exception as e:
            result["error"] = f"RDAP fallback failed: {str(e)}"
    except Exception as e:
        result["error"] = str(e)

    return result


# ── Subdomain Enumeration ────────────────────────────────────────────────────

async def enumerate_subdomains(domain: str) -> dict:
    """Discover subdomains using certificate transparency logs (crt.sh) and DNS brute-force."""
    import httpx

    result = {
        "domain": domain,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "subdomains": [],
        "sources": {}
    }

    found = set()

    # Source 1: crt.sh (Certificate Transparency)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"https://crt.sh/?q=%.{domain}&output=json",
                headers={"User-Agent": "Ombra-Security/1.0"}
            )
            if resp.status_code == 200:
                entries = resp.json()
                for entry in entries:
                    name_value = entry.get("name_value", "")
                    for name in name_value.split("\n"):
                        name = name.strip().lower()
                        if name.endswith(f".{domain}") or name == domain:
                            if "*" not in name:
                                found.add(name)
                result["sources"]["crt_sh"] = len(found)
    except Exception as e:
        result["sources"]["crt_sh"] = f"error: {str(e)}"

    # Source 2: DNS brute-force common prefixes
    common_prefixes = [
        "www", "mail", "ftp", "smtp", "pop", "imap", "webmail", "ns1", "ns2",
        "blog", "dev", "staging", "api", "app", "admin", "portal", "vpn",
        "remote", "test", "demo", "cdn", "static", "assets", "media",
        "git", "gitlab", "jenkins", "ci", "docs", "wiki", "help", "support",
        "shop", "store", "m", "mobile", "beta", "alpha", "stage", "uat",
        "db", "database", "mysql", "postgres", "redis", "mongo", "elastic",
        "grafana", "prometheus", "kibana", "dashboard", "monitor", "status",
    ]
    dns_found = 0
    async def _resolve(prefix):
        nonlocal dns_found
        try:
            fqdn = f"{prefix}.{domain}"
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, socket.gethostbyname, fqdn)
            found.add(fqdn)
            dns_found += 1
        except socket.gaierror:
            pass

    # Run DNS lookups in batches
    for i in range(0, len(common_prefixes), 20):
        batch = common_prefixes[i:i+20]
        await asyncio.gather(*[_resolve(p) for p in batch])
    result["sources"]["dns_bruteforce"] = dns_found

    # Resolve IPs for found subdomains
    resolved = []
    for sub in sorted(found):
        entry = {"subdomain": sub, "ips": []}
        try:
            loop = asyncio.get_event_loop()
            ips = await loop.run_in_executor(None, socket.gethostbyname_ex, sub)
            entry["ips"] = ips[2]
        except Exception:
            pass
        resolved.append(entry)

    result["subdomains"] = resolved
    result["total_found"] = len(resolved)
    return result


# ── Technology Fingerprinting ────────────────────────────────────────────────

def _is_public_ip(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
        return not (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_reserved
            or parsed.is_unspecified
        )
    except ValueError:
        return False


def _is_safe_target_url(raw_url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme not in ("http", "https"):
        return False, "Only http/https URLs are allowed"

    if not parsed.hostname:
        return False, "URL must include a valid hostname"

    try:
        addr_info = socket.getaddrinfo(parsed.hostname, None)
    except Exception:
        return False, "Hostname could not be resolved"

    resolved_ips = {entry[4][0] for entry in addr_info if entry and entry[4]}
    if not resolved_ips:
        return False, "Hostname resolved to no IP addresses"

    for ip in resolved_ips:
        if not _is_public_ip(ip):
            return False, "Target resolves to a non-public IP address"

    return True, ""


async def fingerprint_technology(url: str) -> dict:
    """Detect web technologies, frameworks, servers, and CMS from HTTP response."""
    import httpx

    result = {
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "technologies": [],
        "server_info": {},
        "meta_info": {},
    }

    is_safe, validation_error = _is_safe_target_url(url)
    if not is_safe:
        return {"error": validation_error, "url": url}

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=15, verify=True) as client:
            resp = await client.get(url)
            headers = dict(resp.headers)
            body = resp.text[:100000]
    except Exception as e:
        return {"error": str(e), "url": url}

    techs = []

    # Server header
    server = headers.get("server", "")
    if server:
        result["server_info"]["server"] = server
        techs.append({"name": "Server: " + server, "category": "server", "confidence": "high"})

    powered = headers.get("x-powered-by", "")
    if powered:
        result["server_info"]["x_powered_by"] = powered
        techs.append({"name": powered, "category": "framework", "confidence": "high"})

    # Header-based detection
    header_sigs = {
        "x-drupal-cache": ("Drupal", "cms"),
        "x-generator": (None, "cms"),  # dynamic
        "x-shopify-stage": ("Shopify", "ecommerce"),
        "x-wix-request-id": ("Wix", "cms"),
        "x-vercel-id": ("Vercel", "hosting"),
        "x-amz-cf-id": ("Amazon CloudFront", "cdn"),
        "cf-ray": ("Cloudflare", "cdn"),
        "x-cdn": (None, "cdn"),
        "fly-request-id": ("Fly.io", "hosting"),
        "x-github-request-id": ("GitHub Pages", "hosting"),
        "x-netlify-id": ("Netlify", "hosting"),
    }

    for header, (name, cat) in header_sigs.items():
        val = headers.get(header, "")
        if val:
            detected = name or val
            techs.append({"name": detected, "category": cat, "confidence": "high"})

    # Body-based signatures
    body_sigs = [
        (r'wp-content|wp-includes|wordpress', "WordPress", "cms"),
        (r'Joomla!?|/media/jui/', "Joomla", "cms"),
        (r'content="Drupal', "Drupal", "cms"),
        (r'/sites/default/files', "Drupal", "cms"),
        (r'Shopify\.theme', "Shopify", "ecommerce"),
        (r'<meta name="generator" content="([^"]+)"', None, "cms"),
        (r'react|__NEXT_DATA__|_next/static', "React/Next.js", "framework"),
        (r'ng-version=|ng-app', "Angular", "framework"),
        (r'vue\.js|Vue\.config|__vue', "Vue.js", "framework"),
        (r'nuxt|__NUXT__', "Nuxt.js", "framework"),
        (r'gatsby', "Gatsby", "framework"),
        (r'svelte', "Svelte", "framework"),
        (r'jquery|jQuery', "jQuery", "library"),
        (r'bootstrap\.min\.(css|js)', "Bootstrap", "css_framework"),
        (r'tailwindcss|tailwind', "Tailwind CSS", "css_framework"),
        (r'google-analytics\.com|gtag|GA_TRACKING', "Google Analytics", "analytics"),
        (r'googletagmanager\.com', "Google Tag Manager", "analytics"),
        (r'facebook\.net/en_US/fbevents', "Facebook Pixel", "analytics"),
        (r'cdn\.segment\.com', "Segment", "analytics"),
        (r'hotjar\.com', "Hotjar", "analytics"),
        (r'recaptcha|hcaptcha', "CAPTCHA", "security"),
        (r'cloudflare', "Cloudflare", "cdn"),
        (r'fonts\.googleapis\.com', "Google Fonts", "font"),
        (r'fontawesome|font-awesome', "Font Awesome", "font"),
    ]

    seen = set()
    for pattern, name, cat in body_sigs:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            if name is None:
                detected = m.group(1) if m.lastindex else m.group(0)[:50]
            else:
                detected = name
            if detected.lower() not in seen:
                seen.add(detected.lower())
                techs.append({"name": detected, "category": cat, "confidence": "medium"})

    # Meta tags
    meta_pattern = re.compile(r'<meta\s+(?:name|property)="([^"]+)"\s+content="([^"]*)"', re.IGNORECASE)
    interesting_meta = {"generator", "author", "description", "theme-color", "application-name"}
    for match in meta_pattern.finditer(body[:50000]):
        key = match.group(1).lower()
        if key in interesting_meta:
            result["meta_info"][key] = match.group(2)[:200]

    # Title
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', body, re.IGNORECASE)
    if title_match:
        result["meta_info"]["title"] = title_match.group(1).strip()[:200]

    result["technologies"] = techs
    result["total_detected"] = len(techs)
    result["final_url"] = str(resp.url)
    result["status_code"] = resp.status_code
    return result


# ── Traceroute / Network Path ────────────────────────────────────────────────

async def run_traceroute(host: str, max_hops: int = 20) -> dict:
    """Run traceroute to map the network path to a target."""
    result = {
        "host": host,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "hops": [],
    }

    # Resolve target IP
    try:
        loop = asyncio.get_event_loop()
        target_ip = await loop.run_in_executor(None, socket.gethostbyname, host)
        result["target_ip"] = target_ip
    except socket.gaierror as e:
        return {"error": f"Cannot resolve host: {str(e)}", "host": host}

    # Try traceroute (Linux) or tracert (Windows)
    cmd = ["traceroute", "-m", str(max_hops), "-w", "2", "-n", host]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        raw = stdout.decode(errors="replace")
        result["raw"] = raw

        # Parse traceroute output
        for line in raw.splitlines()[1:]:  # skip header
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                hop_num = int(parts[0])
            except ValueError:
                continue

            hop = {"hop": hop_num, "ip": None, "rtts": []}
            for p in parts[1:]:
                if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', p):
                    hop["ip"] = p
                elif p.replace('.', '').replace('ms', '').strip().isdigit() or re.match(r'[\d.]+', p):
                    try:
                        rtt = float(p.replace('ms', '').strip())
                        hop["rtts"].append(rtt)
                    except ValueError:
                        pass
                elif p == '*':
                    hop["rtts"].append(None)

            if hop["ip"]:
                # Reverse DNS
                try:
                    h = await loop.run_in_executor(None, lambda ip=hop["ip"]: socket.gethostbyaddr(ip))
                    hop["hostname"] = h[0]
                except Exception:
                    hop["hostname"] = None

            result["hops"].append(hop)
    except FileNotFoundError:
        return {"error": "traceroute not installed. Install with: apt install traceroute", "host": host}
    except asyncio.TimeoutError:
        result["error"] = "Traceroute timed out"
    except Exception as e:
        result["error"] = str(e)

    result["total_hops"] = len(result["hops"])
    return result


# ── Banner Grabbing ──────────────────────────────────────────────────────────

async def grab_banners(host: str, ports: List[int] = None) -> dict:
    """Grab service banners from open ports to identify software versions."""
    if ports is None:
        ports = [21, 22, 25, 80, 110, 143, 443, 993, 995, 3306, 5432, 6379, 8080, 8443, 27017]

    result = {
        "host": host,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "banners": [],
    }

    # Resolve host
    try:
        loop = asyncio.get_event_loop()
        ip = await loop.run_in_executor(None, socket.gethostbyname, host)
        result["resolved_ip"] = ip
    except socket.gaierror:
        return {"error": f"Cannot resolve host: {host}", "host": host}

    async def _grab(port):
        banner_info = {"port": port, "banner": None, "service": COMMON_PORTS.get(port, "unknown")}
        try:
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=3)

            # Some services send banner on connect, others need a probe
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=3)
                banner_info["banner"] = data.decode(errors="replace").strip()[:500]
            except asyncio.TimeoutError:
                # Send HTTP probe for web ports
                if port in (80, 8080, 8443, 443, 3000, 5000, 8000, 8001):
                    writer.write(f"HEAD / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
                    await writer.drain()
                    try:
                        data = await asyncio.wait_for(reader.read(2048), timeout=3)
                        banner_info["banner"] = data.decode(errors="replace").strip()[:500]
                    except asyncio.TimeoutError:
                        pass
                else:
                    # Generic probe
                    writer.write(b"\r\n")
                    await writer.drain()
                    try:
                        data = await asyncio.wait_for(reader.read(1024), timeout=2)
                        banner_info["banner"] = data.decode(errors="replace").strip()[:500]
                    except asyncio.TimeoutError:
                        pass

            writer.close()

            if banner_info["banner"]:
                # Extract version info
                version_patterns = [
                    (r'SSH-[\d.]+-(\S+)', 'ssh_version'),
                    (r'Server:\s*(.+)', 'server'),
                    (r'220[- ](.+)', 'ftp_banner'),
                    (r'MySQL|MariaDB|PostgreSQL|Redis|MongoDB', 'database'),
                ]
                for pat, key in version_patterns:
                    m = re.search(pat, banner_info["banner"], re.IGNORECASE)
                    if m:
                        banner_info["detected"] = m.group(0)[:100]
                        break

            return banner_info
        except (ConnectionRefusedError, OSError):
            return None
        except Exception:
            return None

    # Scan all ports concurrently
    tasks = [_grab(port) for port in ports]
    results = await asyncio.gather(*tasks)
    result["banners"] = [r for r in results if r is not None]
    result["total_responsive"] = len(result["banners"])
    return result


# ── Wayback Machine Lookup ───────────────────────────────────────────────────

async def wayback_lookup(url: str, limit: int = 20) -> dict:
    """Check the Internet Archive's Wayback Machine for historical snapshots."""
    import httpx

    result = {
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "snapshots": [],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # CDX API for snapshots
            resp = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url": url,
                    "output": "json",
                    "limit": limit,
                    "fl": "timestamp,original,statuscode,mimetype,length",
                    "collapse": "timestamp:6",  # One per month
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1:
                    headers = data[0]
                    for row in data[1:]:
                        entry = dict(zip(headers, row))
                        ts = entry.get("timestamp", "")
                        entry["wayback_url"] = f"https://web.archive.org/web/{ts}/{entry.get('original', url)}"
                        if ts and len(ts) >= 8:
                            entry["date"] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                        result["snapshots"].append(entry)

            # Availability API
            avail = await client.get(
                "https://archive.org/wayback/available",
                params={"url": url}
            )
            if avail.status_code == 200:
                avail_data = avail.json()
                closest = avail_data.get("archived_snapshots", {}).get("closest")
                if closest:
                    result["latest_snapshot"] = closest

    except Exception as e:
        result["error"] = str(e)

    result["total_snapshots"] = len(result["snapshots"])
    return result


# ── Comprehensive Security Report ────────────────────────────────────────────

async def full_security_scan(host: str = "localhost", project_path: str = None) -> dict:
    """Run all security checks and produce a comprehensive report."""
    report = {
        "scan_id": hashlib.md5(datetime.now(timezone.utc).isoformat().encode()).hexdigest()[:12],
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "host": host
    }
    
    # Run all scans in parallel
    tasks = {
        "port_scan": scan_ports(host),
        "system_audit": audit_system(),
        "log_analysis": analyze_logs(),
    }
    
    if host != "localhost" and host != "127.0.0.1":
        tasks["ssl_check"] = check_ssl(host)
        tasks["http_headers"] = check_http_headers(f"https://{host}")
    
    results = {}
    for name, task in tasks.items():
        try:
            results[name] = await task
        except Exception as e:
            results[name] = {"error": str(e)}
    
    report.update(results)
    
    # Calculate overall score
    scores = []
    if "system_audit" in results and "summary" in results["system_audit"]:
        scores.append(results["system_audit"]["summary"]["score"])
    if "http_headers" in results and "score" in results["http_headers"]:
        scores.append(results["http_headers"]["score"])
    
    port_score = 100
    if "port_scan" in results and "summary" in results["port_scan"]:
        hr = results["port_scan"]["summary"].get("high_risk", 0)
        port_score = max(0, 100 - (hr * 20) - (results["port_scan"]["summary"].get("total_open", 0) * 3))
    scores.append(port_score)
    
    overall = round(sum(scores) / len(scores)) if scores else 0
    report["overall_score"] = overall
    report["overall_grade"] = "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 60 else "D" if overall >= 40 else "F"
    
    return report
