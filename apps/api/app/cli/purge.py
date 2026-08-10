"""Administrative dry-run / purge command.

Usage:
  python -m app.cli.purge --dry-run
  python -m app.cli.purge --execute
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


async def _main(dry_run: bool) -> int:
    from app.db.session import AsyncSessionLocal
    from app.services.retention import run_scheduled_cleanup

    async with AsyncSessionLocal() as session:
        result = await run_scheduled_cleanup(session, dry_run=dry_run)
        await session.commit()
    print(json.dumps(result, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ResearchForge retention cleanup")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible projects without deleting",
    )
    group.add_argument(
        "--execute",
        action="store_true",
        help="Run cleanup for real (idempotent)",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_main(dry_run=bool(args.dry_run)))


if __name__ == "__main__":
    sys.exit(main())
