#!/usr/bin/env python
"""
MAIA Dashboard Setup Script

This script automates the setup and deployment of the MAIA Django dashboard.
It performs the following operations:
- Runs Django migrations for authentication app
- Runs Django migrations for gpu_scheduler app
- Runs general Django migrations
- Applies database migrations
- Starts the Django development server

Usage:
    MAIA_setup_dashboard [--host HOST] [--port PORT] [--no-server]

Options:
    --host HOST         Bind address for the server (default: 0.0.0.0)
    --port PORT         Port number for the server (default: 8000)
    --no-server         Only run migrations, don't start the server
    --background        Run server in background (detached mode)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def get_dashboard_path():
    """Get the path to the dashboard package within the MAIA installation."""
    try:
        import MAIA.dashboard
        dashboard_dir = Path(MAIA.dashboard.__file__).parent
        return dashboard_dir
    except ImportError:
        print("Error: MAIA package not found. Please ensure maia-toolkit is installed.")
        sys.exit(1)


def run_command(command, cwd=None, background=False):
    """Run a command and handle errors."""
    print(f"Running: {' '.join(command)}")
    try:
        if background:
            # Run in background (detached)
            subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            print(f"Command started in background: {' '.join(command)}")
        else:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        sys.exit(1)


def setup_dashboard(host="0.0.0.0", port=8000, skip_server=False, background=False):
    """
    Set up the MAIA dashboard by running migrations and optionally starting the server.
    
    Args:
        host: The host address to bind the server to
        port: The port number to run the server on
        skip_server: If True, only run migrations without starting the server
        background: If True, run the server in background mode
    """
    dashboard_path = get_dashboard_path()
    manage_py = dashboard_path / "manage.py"
    
    if not manage_py.exists():
        print(f"Error: manage.py not found at {manage_py}")
        sys.exit(1)
    
    print(f"Dashboard path: {dashboard_path}")
    print("=" * 60)
    
    # Step 1: Make migrations for authentication app
    print("\n[1/5] Creating migrations for authentication app...")
    run_command([sys.executable, "manage.py", "makemigrations", "authentication"], cwd=dashboard_path)
    
    # Step 2: Make migrations for gpu_scheduler app
    print("\n[2/5] Creating migrations for gpu_scheduler app...")
    run_command([sys.executable, "manage.py", "makemigrations", "gpu_scheduler"], cwd=dashboard_path)
    
    # Step 3: Make general migrations
    print("\n[3/5] Creating general migrations...")
    run_command([sys.executable, "manage.py", "makemigrations"], cwd=dashboard_path)
    
    # Step 4: Apply migrations
    print("\n[4/5] Applying migrations to database...")
    run_command([sys.executable, "manage.py", "migrate"], cwd=dashboard_path)
    
    if not skip_server:
        # Step 5: Start the development server
        print(f"\n[5/5] Starting Django development server on {host}:{port}...")
        server_command = [
            sys.executable,
            "manage.py",
            "runserver",
            f"{host}:{port}",
            "--insecure"
        ]
        
        if background:
            run_command(server_command, cwd=dashboard_path, background=True)
            print(f"\nDashboard server started in background on http://{host}:{port}")
        else:
            print(f"\nStarting dashboard server on http://{host}:{port}")
            print("Press Ctrl+C to stop the server")
            # For foreground server, we don't capture output
            subprocess.run(server_command, cwd=dashboard_path)
    else:
        print("\n[5/5] Skipping server startup (--no-server specified)")
    
    print("=" * 60)
    print("Dashboard setup complete!")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Set up and run the MAIA Django dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address for the server (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number for the server (default: 8000)"
    )
    
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Only run migrations, don't start the server"
    )
    
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run server in background (detached mode)"
    )
    
    args = parser.parse_args()
    
    setup_dashboard(
        host=args.host,
        port=args.port,
        skip_server=args.no_server,
        background=args.background
    )


if __name__ == "__main__":
    main()
