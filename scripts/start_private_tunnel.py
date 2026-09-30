"""User-operated terminal handoff; agents must not run credential entry."""

import argparse
import fcntl
import getpass
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path


def confirm(prompt: str, expected: str) -> None:
    if input(prompt).strip() != expected:
        raise SystemExit("Cancelled; no further actions performed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path, help="Installed tunnel-client binary")
    parser.add_argument("--resume", action="store_true", help="Use this CKAN profile after setup")
    args = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit("Run this yourself in an interactive terminal, outside agent capture.")

    root = Path(__file__).resolve().parents[1]
    binary = args.binary.expanduser().resolve(strict=True)
    server = root / ".venv/bin/ckan-mcp-server"
    if not server.is_file():
        raise SystemExit("Project virtual environment is missing; install dependencies first.")
    state = root / ".local-tunnel"
    credential = state / "runtime-key"
    profiles = state / "profiles"
    profile = profiles / "ckan.yaml"
    os.umask(0o077)

    # Use only this project's settings, never an inherited tunnel or key.
    child_env = {
        "HOME": str(Path.home()),
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "CKAN_URL": "https://ckan0.cf.opendata.inter.prod-toronto.ca",
        "MCP_TRANSPORT": "stdio",
    }
    if args.resume:
        if state.is_symlink() or profiles.is_symlink():
            raise SystemExit("Refusing symlinked private state directories.")
        for path in (state, profiles, credential, profile):
            info = path.lstat()
            if (
                path.is_symlink()
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise SystemExit("Private state ownership/permissions require your review.")
    else:
        if state.exists() or state.is_symlink():
            raise SystemExit(
                "Private state already exists; review it or use --resume. No overwrite."
            )
        tunnel_id = input("Dedicated CKAN tunnel ID (not the LinkedIn Leads tunnel): ").strip()
        if not re.fullmatch(r"tunnel_[a-z0-9]{32}", tunnel_id):
            raise SystemExit(
                "Expected tunnel_ followed by 32 lowercase letters/digits; nothing saved."
            )
        print(f"Credential destination: {credential} (owner-only, mode 0600).")
        print("Use the runtime API key, not an organization admin key.")
        print("Only the CKAN profile will be created; LinkedIn Leads will not be changed.")
        confirm("Type SAVE to authorize saving your runtime key here: ", "SAVE")
        key = getpass.getpass("Paste CKAN runtime key (hidden): ").strip()
        if not key or any(char.isspace() for char in key):
            raise SystemExit("Empty or whitespace-containing key; nothing saved.")
        state.mkdir(mode=0o700)
        profiles.mkdir(mode=0o700)
        fd = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(key + "\n")
        del key
        subprocess.run(
            [
                str(binary),
                "init",
                "--sample",
                "sample_mcp_stdio_local",
                "--profile",
                "ckan",
                "--profile-dir",
                str(profiles),
                "--tunnel-id",
                tunnel_id,
                "--mcp-command",
                shlex.quote(str(server)),
                "--control-plane-api-key-ref",
                f"file:{credential}",
                "--health-listen-addr",
                "127.0.0.1:0",
            ],
            env=child_env,
            cwd=root,
            check=True,
        )

    lock_fd = os.open(state / "run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("This CKAN tunnel is already running; no duplicate started.") from None
    os.set_inheritable(lock_fd, True)

    # The user confirms access at the moment it will occur, including on resume.
    print("Next: contact OpenAI using this CKAN credential, then run the foreground tunnel.")
    print("Keep this terminal open. Ctrl-C stops only this foreground CKAN tunnel.")
    confirm("Type CONNECT to authorize doctor and start: ", "CONNECT")
    common = [
        "--profile",
        "ckan",
        "--profile-dir",
        str(profiles),
        "--mcp.stdio-send-initialized-notification",
        "--log.http-raw-unsafe=false",
    ]
    checked = subprocess.run(
        [str(binary), "doctor", *common, "--explain"],
        env=child_env,
        cwd=root,
    )
    if checked.returncode:
        raise SystemExit(
            "Doctor failed; stopped before startup. Resolve access/configuration first."
        )
    command = [
        str(binary),
        "run",
        *common,
        "--health.url-file",
        str(state / "health.url"),
        "--pid.file",
        str(state / "tunnel.pid"),
    ]
    os.chdir(root)
    os.execve(binary, command, child_env)


if __name__ == "__main__":
    main()
