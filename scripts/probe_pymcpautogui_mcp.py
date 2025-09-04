"""
Probe PyMCPAutoGUI MCP server via stdio and list tools.

This script launches `python -m pymcpautogui.server` and performs a minimal
MCP JSON-RPC handshake over stdio, then calls `tools/list` and prints tool IDs.

Usage: python scripts/probe_pymcpautogui_mcp.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Any, Dict, Optional


def _write_message(proc: subprocess.Popen[bytes], message: Dict[str, Any]) -> None:
    data = json.dumps(message, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
    if not proc.stdin:
        raise RuntimeError("No stdin for server process")
    proc.stdin.write(header)
    proc.stdin.write(data)
    proc.stdin.flush()


def _read_message(proc: subprocess.Popen[bytes], timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """Read a single JSON-RPC message framed by MCP headers from stdout."""
    if not proc.stdout:
        raise RuntimeError("No stdout for server process")

    start = time.time()
    buffer = b""
    # Read headers
    while b"\r\n\r\n" not in buffer:
        if time.time() - start > timeout:
            return None
        chunk = proc.stdout.read(1)
        if not chunk:
            time.sleep(0.01)
            continue
        buffer += chunk

    header_blob, rest = buffer.split(b"\r\n\r\n", 1)
    headers = header_blob.decode("ascii", errors="replace").split("\r\n")
    content_length = None
    for line in headers:
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":", 1)[1].strip())
            except Exception:
                pass
            break
    if content_length is None:
        return None

    # Read body, including any bytes already placed in 'rest'
    body = rest
    while len(body) < content_length:
        if time.time() - start > timeout:
            return None
        chunk = proc.stdout.read(content_length - len(body))
        if not chunk:
            time.sleep(0.01)
            continue
        body += chunk

    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def main() -> int:
    server_cmd = [sys.executable, "-m", "pymcpautogui.server"]

    try:
        proc = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("python executable not found", file=sys.stderr)
        return 127
    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        return 1

    try:
        # Quick check if process failed immediately (e.g., module not found)
        time.sleep(0.2)
        rc = proc.poll()
        if rc is not None and rc != 0:
            err = b""
            if proc.stderr:
                try:
                    err = proc.stderr.read() or b""
                except Exception:
                    err = b""
            sys.stderr.write("PyMCPAutoGUI server exited early.\n")
            sys.stderr.write(err.decode("utf-8", errors="replace"))
            return rc if isinstance(rc, int) else 1

        # Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "probe", "version": "0.1.0"},
                "capabilities": {},
            },
        }
        _write_message(proc, init_req)

        # Read until we get a response to id=0
        init_resp: Optional[Dict[str, Any]] = None
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if proc.poll() not in (None, 0):
                break
            msg = _read_message(proc, timeout=deadline - time.time())
            if msg is None:
                continue
            if msg.get("id") == 0:
                init_resp = msg
                break
        if not init_resp or "result" not in init_resp:
            print("initialize failed or timed out", file=sys.stderr)
            if proc.stderr:
                try:
                    err = proc.stderr.read() or b""
                    if err:
                        sys.stderr.write(err.decode("utf-8", errors="replace"))
                except Exception:
                    pass
            return 2

        # Send optional 'initialized' notification
        _write_message(
            proc,
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        )

        # tools/list
        tools_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        _write_message(proc, tools_req)

        tools_resp: Optional[Dict[str, Any]] = None
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if proc.poll() not in (None, 0):
                break
            msg = _read_message(proc, timeout=deadline - time.time())
            if msg is None:
                continue
            if msg.get("id") == 1:
                tools_resp = msg
                break

        if not tools_resp or "result" not in tools_resp:
            print("tools/list failed or timed out", file=sys.stderr)
            if proc.stderr:
                try:
                    err = proc.stderr.read() or b""
                    if err:
                        sys.stderr.write(err.decode("utf-8", errors="replace"))
                except Exception:
                    pass
            return 3

        result = tools_resp["result"]
        tools = result.get("tools", []) if isinstance(result, dict) else []
        if not tools:
            print("No tools reported by PyMCPAutoGUI.")
        else:
            print("PyMCPAutoGUI tools:")
            for t in tools:
                tid = t.get("name") or t.get("id") or t.get("title")
                print(f"- {tid}")

        return 0
    finally:
        try:
            _write_message(
                proc,
                {"jsonrpc": "2.0", "id": 9, "method": "shutdown"},
            )
        except Exception:
            pass
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
