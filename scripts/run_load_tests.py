#!/usr/bin/env python
"""Run Load Tests Script.

This script provides a convenient interface for running Locust load tests
against the Django Ninja API.

Usage:
    python scripts/run_load_tests.py                    # Interactive mode
    python scripts/run_load_tests.py --quick            # Quick test (10 users, 30s)
    python scripts/run_load_tests.py --users 50 --duration 2m
    python scripts/run_load_tests.py --report           # Generate HTML report

Environment Variables:
    TEST_BASE_URL: Target URL (default: http://localhost:8000)
    TEST_USER_EMAIL: Email for authenticated tests
    TEST_USER_PASSWORD: Password for authenticated tests
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
LOCUSTFILE = PROJECT_ROOT / "tests" / "load" / "locustfile.py"
REPORTS_DIR = PROJECT_ROOT / "reports"


def check_locust_installed() -> bool:
    """Check if Locust is installed."""
    try:
        subprocess.run(
            ["locust", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_locust():
    """Install Locust using uv."""
    print("Installing Locust...")
    subprocess.run(
        ["uv", "pip", "install", "locust"],
        check=True,
    )


def run_locust(
    host: str,
    users: int,
    spawn_rate: int,
    duration: str,
    headless: bool = True,
    html_report: str | None = None,
    csv_prefix: str | None = None,
    extra_args: list[str] | None = None,
) -> int:
    """Run Locust load tests.

    Args:
        host: Target host URL.
        users: Number of concurrent users.
        spawn_rate: User spawn rate per second.
        duration: Test duration (e.g., "30s", "2m", "1h").
        headless: Run without web UI.
        html_report: Path for HTML report.
        csv_prefix: Prefix for CSV report files.
        extra_args: Additional Locust arguments.

    Returns:
        int: Exit code from Locust.
    """
    cmd = [
        "locust",
        "-f",
        str(LOCUSTFILE),
        "--host",
        host,
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "-t",
        duration,
    ]

    if headless:
        cmd.append("--headless")

    if html_report:
        cmd.extend(["--html", html_report])

    if csv_prefix:
        cmd.extend(["--csv", csv_prefix])

    if extra_args:
        cmd.extend(extra_args)

    print("=" * 60)
    print("Running Load Test")
    print("=" * 60)
    print(f"Target:     {host}")
    print(f"Users:      {users}")
    print(f"Spawn rate: {spawn_rate}/s")
    print(f"Duration:   {duration}")
    if html_report:
        print(f"Report:     {html_report}")
    print("=" * 60)
    print()

    result = subprocess.run(cmd, check=False)
    return result.returncode


def parse_duration(duration_str: str) -> str:
    """Parse and validate duration string.

    Args:
        duration_str: Duration string (e.g., "30s", "2m", "1h").

    Returns:
        str: Validated duration string.

    Raises:
        ValueError: If duration format is invalid.
    """
    duration_str = duration_str.strip().lower()

    # Check for valid format
    if duration_str[-1] not in ["s", "m", "h"]:
        msg = "Duration must end with 's' (seconds), 'm' (minutes), or 'h' (hours)"
        raise ValueError(msg)

    try:
        int(duration_str[:-1])
    except ValueError:
        msg = "Duration must be a number followed by s/m/h"
        raise

    return duration_str


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Locust load tests for the Django Ninja API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_load_tests.py                        # Interactive web UI
    python scripts/run_load_tests.py --quick                # Quick test
    python scripts/run_load_tests.py -u 50 -t 2m            # 50 users, 2 minutes
    python scripts/run_load_tests.py --stress               # Stress test
    python scripts/run_load_tests.py --report               # Generate report
        """,
    )

    # Target configuration
    parser.add_argument(
        "--host",
        default=os.environ.get("TEST_BASE_URL", "http://localhost:8000"),
        help="Target host URL (default: http://localhost:8000)",
    )

    # Test configuration
    parser.add_argument(
        "-u",
        "--users",
        type=int,
        default=10,
        help="Number of concurrent users (default: 10)",
    )
    parser.add_argument(
        "-r",
        "--spawn-rate",
        type=int,
        default=2,
        help="User spawn rate per second (default: 2)",
    )
    parser.add_argument(
        "-t",
        "--duration",
        default="30s",
        help="Test duration (e.g., 30s, 2m, 1h) (default: 30s)",
    )

    # Quick presets
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test: 10 users, 30 seconds",
    )
    parser.add_argument(
        "--moderate",
        action="store_true",
        help="Moderate test: 50 users, 2 minutes",
    )
    parser.add_argument(
        "--heavy",
        action="store_true",
        help="Heavy test: 100 users, 5 minutes",
    )
    parser.add_argument(
        "--stress",
        action="store_true",
        help="Stress test: 200 users, 10 minutes",
    )

    # Output options
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Generate CSV reports",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=REPORTS_DIR,
        help=f"Report output directory (default: {REPORTS_DIR})",
    )

    # Mode options
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run with web UI (interactive mode)",
    )

    # Debug options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show command without running",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install Locust if not present",
    )

    args = parser.parse_args()

    # Check/install Locust
    if not check_locust_installed():
        if args.install:
            install_locust()
        else:
            print("Error: Locust is not installed.")
            print("Run with --install to install it, or run:")
            print("  uv add locust")
            sys.exit(1)

    # Apply presets
    if args.quick:
        args.users = 10
        args.spawn_rate = 2
        args.duration = "30s"
    elif args.moderate:
        args.users = 50
        args.spawn_rate = 5
        args.duration = "2m"
    elif args.heavy:
        args.users = 100
        args.spawn_rate = 10
        args.duration = "5m"
    elif args.stress:
        args.users = 200
        args.spawn_rate = 20
        args.duration = "10m"

    # Validate duration
    try:
        duration = parse_duration(args.duration)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Setup report paths
    html_report = None
    csv_prefix = None

    if args.report or args.csv:
        # Create reports directory
        args.report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if args.report:
            html_report = str(args.report_dir / f"load_test_{timestamp}.html")

        if args.csv:
            csv_prefix = str(args.report_dir / f"load_test_{timestamp}")

    # Check if locustfile exists
    if not LOCUSTFILE.exists():
        print(f"Error: Locustfile not found at {LOCUSTFILE}")
        sys.exit(1)

    # Dry run - show command
    if args.dry_run:
        cmd = [
            "locust",
            "-f",
            str(LOCUSTFILE),
            "--host",
            args.host,
            "-u",
            str(args.users),
            "-r",
            str(args.spawn_rate),
            "-t",
            duration,
        ]
        if not args.web:
            cmd.append("--headless")
        if html_report:
            cmd.extend(["--html", html_report])
        if csv_prefix:
            cmd.extend(["--csv", csv_prefix])

        print("Would run:")
        print(" ".join(cmd))
        sys.exit(0)

    # Run the load test
    exit_code = run_locust(
        host=args.host,
        users=args.users,
        spawn_rate=args.spawn_rate,
        duration=duration,
        headless=not args.web,
        html_report=html_report,
        csv_prefix=csv_prefix,
    )

    # Print report location
    if html_report and exit_code == 0:
        print()
        print("=" * 60)
        print(f"HTML Report: {html_report}")
        print("=" * 60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
