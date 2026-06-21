from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
APP_SERVICES = ["postgres", "redis", "api", "worker", "frontend"]
WORKER_SERVICES = ["postgres", "redis", "api", "worker", "frontend"]
BOT_SERVICES = ["postgres", "redis", "api", "worker", "frontend", "bot"]
ALL_SERVICES = ["postgres", "redis", "api", "worker", "frontend", "bot"]
DOCKER_COMPOSE_ATTEMPTS = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start Paper First local services")
    parser.add_argument("--bot", action="store_true", help="start Telegram bot with the app")
    parser.add_argument("--worker", action="store_true", help="start background worker with the app")
    parser.add_argument("--all", action="store_true", help="start app, worker and Telegram bot")
    parser.add_argument("--no-build", action="store_true", help="skip Docker image rebuild")
    parser.add_argument("-d", "--detach", action="store_true", help="run containers in the background")
    parser.add_argument("--dry-run", action="store_true", help="print docker compose command without running it")
    return parser


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


def run_with_retry(command: list[str], env: dict[str, str]) -> int:
    for attempt in range(1, DOCKER_COMPOSE_ATTEMPTS + 1):
        completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
        if completed.returncode == 0 or attempt == DOCKER_COMPOSE_ATTEMPTS:
            return completed.returncode

        print("docker compose failed; retrying once...", file=sys.stderr)

    return 1


def main() -> int:
    args = build_parser().parse_args()
    command = build_command(args)
    printable_command = " ".join(command)
    command_env = os.environ.copy()
    command_env["COMPOSE_MENU"] = "false"
    command_env["DOCKER_CLI_HINTS"] = "false"
    if args.dry_run:
        print(printable_command)
        return 0

    try:
        print(f"running: {printable_command}")
        return run_with_retry(command, command_env)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
