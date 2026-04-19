"""Tiny SSH driver wrapping paramiko for the doomedash.com deploy.

Usage:
    python deploy/remote.py run  server-a 'uname -a'
    python deploy/remote.py put  server-a local_file /remote/path
    python deploy/remote.py rtree server-a local_dir /remote/path   # recursive upload
"""
from __future__ import annotations

import os
import posixpath
import sys
from pathlib import Path

# Windows cp1251 console can't print unicode arrows from systemd output.
try:
    sys.stdout.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
except Exception:
    pass

import paramiko


HOSTS: dict[str, dict[str, str]] = {
    "server-a": {"host": "144.31.136.67", "user": "root", "password": os.environ.get("SRV_A_PW", "")},
    "server-b": {"host": "144.31.136.4",  "user": "root", "password": os.environ.get("SRV_B_PW", "")},
}


def _client(name: str) -> paramiko.SSHClient:
    cfg = HOSTS[name]
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(
        hostname=cfg["host"],
        username=cfg["user"],
        password=cfg["password"],
        look_for_keys=False,
        allow_agent=False,
        timeout=15,
    )
    return cli


def run_cmd(name: str, cmd: str, *, echo: bool = True, check: bool = False) -> tuple[int, str, str]:
    cli = _client(name)
    try:
        stdin, stdout, stderr = cli.exec_command(cmd, get_pty=False, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
    finally:
        cli.close()
    if echo:
        if out:
            sys.stdout.write(out)
            if not out.endswith("\n"):
                sys.stdout.write("\n")
        if err:
            sys.stderr.write(err)
            if not err.endswith("\n"):
                sys.stderr.write("\n")
    if check and rc != 0:
        raise RuntimeError(f"[{name}] `{cmd}` exited {rc}: {err[:300]}")
    return rc, out, err


def put_file(name: str, local: str | Path, remote: str) -> None:
    local = Path(local)
    cli = _client(name)
    try:
        sftp = cli.open_sftp()
        try:
            # Ensure remote dir exists
            rdir = posixpath.dirname(remote)
            if rdir:
                _mkdirs_sftp(sftp, rdir)
            sftp.put(str(local), remote)
        finally:
            sftp.close()
    finally:
        cli.close()
    print(f"[{name}] uploaded {local} -> {remote}")


def put_tree(name: str, local_dir: str | Path, remote_dir: str,
             excludes: set[str] | None = None) -> None:
    """Recursively upload a directory. Skips names in ``excludes``."""
    local_dir = Path(local_dir).resolve()
    excludes = excludes or set()
    cli = _client(name)
    uploaded = 0
    try:
        sftp = cli.open_sftp()
        try:
            _mkdirs_sftp(sftp, remote_dir)
            for root, dirs, files in os.walk(local_dir):
                # prune excluded directories in-place
                dirs[:] = [d for d in dirs if d not in excludes]
                rel = Path(root).relative_to(local_dir)
                rpath = posixpath.join(remote_dir, *rel.parts) if rel.parts else remote_dir
                if rel.parts:
                    _mkdirs_sftp(sftp, rpath)
                for f in files:
                    if f in excludes:
                        continue
                    lp = Path(root) / f
                    rp = posixpath.join(rpath, f)
                    try:
                        sftp.put(str(lp), rp)
                        uploaded += 1
                    except Exception as exc:
                        print(f"[{name}] WARN: failed to upload {lp}: {exc!r}", file=sys.stderr)
        finally:
            sftp.close()
    finally:
        cli.close()
    print(f"[{name}] uploaded {uploaded} files -> {remote_dir}")


def _mkdirs_sftp(sftp: paramiko.SFTPClient, path: str) -> None:
    """Recursive mkdir over SFTP."""
    if not path or path == "/":
        return
    try:
        sftp.stat(path)
        return
    except FileNotFoundError:
        pass
    parent = posixpath.dirname(path)
    if parent and parent != path:
        _mkdirs_sftp(sftp, parent)
    try:
        sftp.mkdir(path)
    except OSError:
        # race / exists
        pass


# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    verb = sys.argv[1]
    name = sys.argv[2]
    if name not in HOSTS:
        print(f"unknown host: {name}. Known: {list(HOSTS.keys())}")
        return 2
    if not HOSTS[name]["password"]:
        print(f"ERROR: set SRV_{name[-1].upper()}_PW environment variable first")
        return 2
    try:
        if verb == "run":
            cmd = " ".join(sys.argv[3:])
            rc, _, _ = run_cmd(name, cmd)
            return rc
        if verb == "put":
            put_file(name, sys.argv[3], sys.argv[4])
            return 0
        if verb == "rtree":
            excludes = {".venv", "node_modules", "__pycache__", ".git",
                        ".pytest_cache", ".mypy_cache", "dist-tsc-node"}
            put_tree(name, sys.argv[3], sys.argv[4], excludes=excludes)
            return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
