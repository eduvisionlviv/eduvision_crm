"""Utilities for registering Flask blueprints only once."""
from __future__ import annotations

from typing import Iterable, Set, Tuple

from flask import Blueprint

_REGISTRY_KEY = "auto_registered_blueprints"


def _registry(app) -> Set[Tuple[str, str]]:
    return app.extensions.setdefault(_REGISTRY_KEY, set())


def _blueprint_id(bp: Blueprint) -> Tuple[str, str]:
    return (bp.name or "", getattr(bp, "import_name", ""))


def register_blueprints(app, blueprints: Iterable[Blueprint], source: str, logger=None, printer=print) -> None:
    """Register each blueprint once per app."""
    reg = _registry(app)
    for bp in blueprints:
        if not bp:
            continue
        ident = _blueprint_id(bp)
        if ident in reg:
            msg = f"↺  Skip duplicate blueprint {bp.name!r} from {source}"
            if logger:
                logger.info(msg)
            else:
                printer(msg)
            continue
        app.register_blueprint(bp)
        reg.add(ident)
        msg = f"✅ Blueprint {bp.name!r} loaded from {source}"
        if logger:
            logger.info(msg)
        else:
            printer(msg)
