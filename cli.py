# -*- coding: utf-8 -*-
"""Console script entry points for NerpyBot."""

import sys
from pathlib import Path


def _run_alembic(config_file: str) -> None:
    try:
        from alembic.config import main as alembic_main
    except ImportError:
        print("alembic not installed. Run: uv sync --group migrations", file=sys.stderr)
        sys.exit(1)
    alembic_main(argv=["-c", config_file, *sys.argv[1:]])


def alembic_nerpybot() -> None:
    """Run Alembic with the NerpyBot (full deployment) config."""
    _run_alembic("alembic-nerpybot.ini")


def alembic_humanmusic() -> None:
    """Run Alembic with the HumanMusic (music-only) config."""
    _run_alembic("alembic-humanmusic.ini")


def bot() -> None:
    """Run the NerpyBot Discord bot."""
    # NerdyPy/ must be on sys.path so internal imports (models, utils, modules) resolve.
    nerdypy_dir = str(Path(__file__).resolve().parent / "NerdyPy")
    if nerdypy_dir not in sys.path:
        sys.path.insert(0, nerdypy_dir)

    from NerdyPy import main

    main()
