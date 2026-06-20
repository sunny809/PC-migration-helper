#!/usr/bin/env python3
"""PC Migration Helper - Entry Point

PC迁移助手 - 入口文件

A desktop application for scanning and migrating personal files
on Windows systems. Discovers personal documents (excluding system
and application files), lists them for review, and provides
compression and copy functionality to migration targets like
USB drives.

Usage:
    python main.py [--debug]
"""

import sys


def main():
    """Application entry point."""
    # Parse simple CLI arguments
    debug = "--debug" in sys.argv

    # Setup logging
    from src.utils.logger import setup_logging
    logger = setup_logging(debug=debug)

    logger.info("PC Migration Helper starting...")

    # Create and run the application
    from src.app import create_app, run_app

    app = create_app()
    exit_code = run_app(app)

    logger.info(f"PC Migration Helper exiting with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
