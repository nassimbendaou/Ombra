"""
Ombra Filesystem Tool
- Permission-gated file read/write
- Path sanitization + safety checks
- Activity logging
"""
import os
import stat

# Safe base directories
SAFE_DIRS = ["/tmp", "/app"]
BLOCKED_PATHS = ["/etc/passwd", "/etc/shadow", ".env", "id_rsa", ".ssh"]


def sanitize_path(filepath: str) -> str:
    """Sanitize and validate file path."""
    filepath = os.path.normpath(filepath)
    filepath = os.path.abspath(filepath)
    
    # Block dangerous paths
    for blocked in BLOCKED_PATHS:
        if blocked in filepath:
            raise ValueError(f"Blocked path pattern: {blocked}")
    
    # Check if within safe directories
    is_safe = any(filepath.startswith(safe_dir) for safe_dir in SAFE_DIRS)
    if not is_safe:
        raise ValueError(f"Path {filepath} is outside allowed directories: {SAFE_DIRS}")
    
    return filepath


def read_file(filepath: str, max_size: int = 1024 * 1024) -> dict:
    """Read a file safely."""
    try:
        filepath = sanitize_path(filepath)
        
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File not found: {filepath}"}
        
        file_size = os.path.getsize(filepath)
        if file_size > max_size:
            return {"success": False, "error": f"File too large: {file_size} bytes (max: {max_size})"}
        
        with open(filepath, 'r', errors='replace') as f:
            content = f.read()
        
        return {
            "success": True,
            "path": filepath,
            "content": content,
            "size": file_size,
            "lines": content.count('\n') + 1
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(filepath: str, content: str, create_dirs: bool = True) -> dict:
    """Write a file safely."""
    try:
        filepath = sanitize_path(filepath)
        
        if create_dirs:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": filepath,
            "size": len(content),
            "lines": content.count('\n') + 1
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_directory(dirpath: str, max_depth: int = 2) -> dict:
    """List directory contents safely."""
    try:
        dirpath = sanitize_path(dirpath)
        
        if not os.path.isdir(dirpath):
            return {"success": False, "error": f"Not a directory: {dirpath}"}
        
        items = []
        for entry in os.scandir(dirpath):
            items.append({
                "name": entry.name,
                "path": entry.path,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0
            })
        
        items.sort(key=lambda x: (not x["is_dir"], x["name"]))
        return {"success": True, "path": dirpath, "items": items[:100]}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
