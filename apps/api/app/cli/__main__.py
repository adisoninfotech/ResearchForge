"""python -m app.cli delegates to purge by default when submodule is used."""

from app.cli.purge import main

raise SystemExit(main())
