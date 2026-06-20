from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
NGROK_CONFIG = PROJECT_ROOT / "ngrok.yml"
NGROK_ENDPOINT_NAME = "app"
NGROK_API_URL = "http://127.0.0.1:4040/api/tunnels"
APP_SERVICES = ["postgres", "redis", "api", "frontend"]
WORKER_SERVICES = ["postgres", "redis", "api", "worker", "frontend"]
BOT_SERVICES = ["postgres", "redis", "api", "frontend", "bot"]
ALL_SERVICES = ["postgres", "redis", "api", "worker", "frontend", "bot"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start Paper First local services")
    parser.add_argument("--bot", action="store_true", help="start Telegram bot with the app")
    parser.add_argument("--worker", action="store_true", help="start background worker with the app")
    parser.add_argument("--all", action="store_true", help="start app, worker, Telegram bot and ngrok")
    parser.add_argument("--no-build", action="store_true", help="skip Docker image rebuild")
    parser.add_argument("-d", "--detach", action="store_true", help="run containers in the background")
    parser.add_argument("--ngrok", action="store_true", help="start HTTPS ngrok tunnel for localhost:5173")
    parser.add_argument("--dry-run", action="store_true", help="print docker compose command without running it")
    return parser


def read_env_value(name: str, env_file: Path = ENV_FILE) -> str | None:
    value = os.environ.get(name)
    if value is not None:
        return value
    if not env_file.exists():
        return None

    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if key == name:
            return value.strip().strip("'\"")

    return None


def build_command(args: argparse.Namespace) -> list[str]:
    command = ["docker", "compose"]
    if args.bot or args.all:
        command.extend(["--profile", "bot"])

    command.append("up")
    if not args.no_build:
        command.append("--build")
    if args.detach:
        command.append("--detach")

    if args.all:
        command.extend(ALL_SERVICES)
    elif args.bot:
        command.extend(BOT_SERVICES)
    elif args.worker:
        command.extend(WORKER_SERVICES)
    else:
        command.extend(APP_SERVICES)
    return command


def wait_for_ngrok_url(process: subprocess.Popen[bytes]) -> str:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("ngrok завершился до выдачи публичного URL")
        try:
            with urllib.request.urlopen(NGROK_API_URL, timeout=1) as response:
                payload = json.loads(response.read().decode())
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            time.sleep(0.5)
            continue

        for tunnel in payload.get("tunnels", []):
            public_url = tunnel.get("public_url", "")
            if public_url.startswith("https://"):
                return public_url
        time.sleep(0.5)

    raise RuntimeError("ngrok не отдал HTTPS URL за 15 секунд")


def start_ngrok() -> tuple[subprocess.Popen[bytes], str]:
    token = read_env_value("NGROK_AUTH_TOKEN")
    if not token:
        raise RuntimeError("NGROK_AUTH_TOKEN не задан в окружении или .env")
    if not NGROK_CONFIG.exists():
        raise RuntimeError(f"не найден {NGROK_CONFIG.name}")

    env = os.environ.copy()
    env["NGROK_AUTHTOKEN"] = token
    process = subprocess.Popen(
        ["ngrok", "start", NGROK_ENDPOINT_NAME, "--config", str(NGROK_CONFIG), "--log", "false"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    return process, wait_for_ngrok_url(process)


def stop_ngrok(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    args = build_parser().parse_args()
    command = build_command(args)
    printable_command = " ".join(command)
    command_env = os.environ.copy()
    start_tunnel = args.ngrok or args.all
    if args.dry_run:
        if start_tunnel:
            print(f"NGROK_AUTHTOKEN=*** ngrok start {NGROK_ENDPOINT_NAME} --config {NGROK_CONFIG.name}")
        print(printable_command)
        return 0
    if start_tunnel and args.detach:
        print("ngrok нельзя использовать с --detach: туннель живет, пока работает start.py", file=sys.stderr)
        return 2

    ngrok_process = None
    try:
        if start_tunnel:
            ngrok_process, public_url = start_ngrok()
            command_env["PAPERFIRST_TELEGRAM_WEB_APP_URL"] = public_url
            command_env["PAPERFIRST_BACKEND_CORS_ORIGINS"] = json.dumps([public_url])
            print(f"ngrok: {public_url}")

        print(f"running: {printable_command}")
        completed = subprocess.run(command, cwd=PROJECT_ROOT, env=command_env)
        return completed.returncode
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if ngrok_process is not None:
            stop_ngrok(ngrok_process)


if __name__ == "__main__":
    sys.exit(main())
