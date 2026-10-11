"""Start and stop the Pi agent over SSH, so nobody has to SSH in by hand."""

from __future__ import annotations

import socket
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent
REMOTE_DIR = "skatectl"
# Uploaded fresh on every start, so the Pi always runs the laptop's version.
UPLOADS = {
    ROOT / "backend" / "pi_agent.py": "pi_agent.py",
    ROOT / "sensor" / "mpu6050.py": "mpu6050.py",
}
# Only one program may read the MPU-6050, so stop the manual scripts too.
STOP_CMD = (
    "pkill -f skatectl/pi_agent.py; pkill -f scripts/pi_sender.py; "
    "pkill -f scripts/test_controller.py; sleep 0.3"
)
CONNECT_TIMEOUT_S = 6


class PiError(Exception):
    """A short, human-readable reason the Pi could not be started."""


def laptop_ip_for(pi_host: str) -> str:
    """The laptop address the Pi can reach (the hotspot interface)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((pi_host, 9))
        return probe.getsockname()[0]
    except OSError as exc:
        raise PiError(f"No network route to the Pi ({pi_host}). Join the hotspot.") from exc
    finally:
        probe.close()


def _connect(host: str, user: str, password: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username=user, password=password, timeout=CONNECT_TIMEOUT_S,
                       banner_timeout=CONNECT_TIMEOUT_S, auth_timeout=CONNECT_TIMEOUT_S,
                       look_for_keys=False, allow_agent=False)
    except paramiko.AuthenticationException as exc:
        raise PiError("Pi rejected the login. Check the password.") from exc
    except (OSError, paramiko.SSHException) as exc:
        raise PiError(f"Can't reach the Pi at {host}. Is it on and on the hotspot?") from exc
    return client


def start_agent(host: str, user: str, password: str, udp_port: int, cam_port: int) -> str:
    """Upload and (re)start the agent. Returns the laptop IP it streams to."""
    laptop_ip = laptop_ip_for(host)
    client = _connect(host, user, password)
    try:
        client.exec_command(f"mkdir -p {REMOTE_DIR}")[1].channel.recv_exit_status()
        sftp = client.open_sftp()
        for local, remote in UPLOADS.items():
            sftp.put(str(local), f"{REMOTE_DIR}/{remote}")
        sftp.close()
        client.exec_command(STOP_CMD)[1].channel.recv_exit_status()
        cmd = (
            f"nohup python3 -u {REMOTE_DIR}/pi_agent.py --host {laptop_ip} "
            f"--port {udp_port} --cam-port {cam_port} > {REMOTE_DIR}/agent.log 2>&1 &"
        )
        client.exec_command(cmd)[1].channel.recv_exit_status()
    finally:
        client.close()
    return laptop_ip


def agent_log_tail(host: str, user: str, password: str) -> str:
    """Last line of the agent log, for a short error hint."""
    client = _connect(host, user, password)
    try:
        _, out, _ = client.exec_command(f"tail -n 1 {REMOTE_DIR}/agent.log")
        return out.read().decode(errors="replace").strip()
    finally:
        client.close()


def stop_agent(host: str, user: str, password: str) -> None:
    client = _connect(host, user, password)
    try:
        client.exec_command("pkill -f skatectl/pi_agent.py")[1].channel.recv_exit_status()
    finally:
        client.close()
