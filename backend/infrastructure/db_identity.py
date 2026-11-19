"""Mutation-target identity for destructive operations.

R-1: a configured URL is not proof of the database a connection is actually
attached to. This module asks the *live connection* who it is and refuses the
destructive operation unless that answer matches trusted configuration or the
target is positively marked disposable.

Trust model:
* ``EIMS_DB_IDENTITY`` (``"<database>|<role>"``) is process configuration, set by
  the operator before start-up. It is never read from request data.
* With no expected identity, a target is accepted only when PostgreSQL itself
  reports the database comment sentinel written by the disposable provisioner.
  A URL, a hostname, a database name suffix or an environment flag alone is not
  evidence.

Ordinary CRUD is not gated here: doing so without a deployed expected identity
would break normal writes. The gate covers destructive/admin paths, where the
blast radius is.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from sqlalchemy import text

_unconfigured_warned = False

IDENTITY_ENV = "EIMS_DB_IDENTITY"
REQUIRED_ENV = "EIMS_DB_IDENTITY_REQUIRED"
DISPOSABLE_PREFIX = "EIMS-DISPOSABLE-"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"", "0", "false", "no", "off"}


def required_enabled() -> bool:
    """Parses ``EIMS_DB_IDENTITY_REQUIRED`` strictly; unknown values are an error."""
    raw = (os.environ.get(REQUIRED_ENV) or "").strip().lower()
    if raw in _FALSE_VALUES:
        return False
    if raw in _TRUE_VALUES:
        return True
    raise MutationTargetError(
        f"malformed {REQUIRED_ENV}; expected 0 or 1 (got {raw!r})")


def identity_enforcement_expected() -> bool:
    """True when a live identity check is meaningful for this process."""
    return bool((os.environ.get(IDENTITY_ENV) or "").strip()) or required_enabled()


class MutationTargetError(RuntimeError):
    """The live connection is not an accepted target for a destructive action."""


@dataclass(frozen=True)
class ConnectionIdentity:
    database: str | None
    user: str | None
    session_user: str | None
    database_comment: str | None

    @property
    def disposable(self) -> bool:
        return bool(self.database_comment and self.database_comment.startswith(DISPOSABLE_PREFIX))

    def matches(self, expected: str) -> bool:
        return f"{self.database}|{self.user}" == expected


def validate_runtime_identity_configuration() -> None:
    """Fail fast at process start; a request-time check is too late.

    * ``REQUIRED=1`` with no ``EIMS_DB_IDENTITY`` is a configuration error.
    * A malformed identity is a configuration error regardless of REQUIRED.
    * Unconfigured + not required stays supported, but is never "verified".
    """
    expected = (os.environ.get(IDENTITY_ENV) or "").strip()
    required = required_enabled()
    if not expected:
        if required:
            raise MutationTargetError(
                f"{REQUIRED_ENV}=1 requires {IDENTITY_ENV}='<database>|<role>'")
        return
    if expected.count("|") != 1 or not all(part.strip() for part in expected.split("|")):
        raise MutationTargetError(f"malformed {IDENTITY_ENV}; expected '<database>|<role>'")


async def connection_identity(session) -> ConnectionIdentity:
    """Ask the live session; never derives identity from configuration."""
    row = (await session.execute(text(
        "SELECT current_database(), current_user, session_user, "
        "shobj_description(oid, 'pg_database') FROM pg_database "
        "WHERE datname = current_database()"
    ))).first()
    if row is None:
        raise MutationTargetError("identity query returned no row")
    return ConnectionIdentity(str(row[0]), str(row[1]), str(row[2]), row[3])


async def require_runtime_identity(session) -> ConnectionIdentity | None:
    """Policy A at the application session boundary.

    Every API request obtains its session from one dependency, so this runs once
    per request on the connection that request will use.

    * ``EIMS_DB_IDENTITY`` set  -> the live connection must match it, or the
      request fails before any statement runs.
    * not set                    -> allowed only when the deployment explicitly
      accepts the gap (``EIMS_DB_IDENTITY_REQUIRED`` unset/0); the session is
      marked ``unconfigured`` so readiness and the acceptance matrix cannot
      silently report compliance.
    * ``EIMS_DB_IDENTITY_REQUIRED=1`` -> missing/malformed configuration fails
      closed.
    """
    cached = session.info.get("eims_identity")
    if cached is not None:
        return cached
    expected = (os.environ.get(IDENTITY_ENV) or "").strip()
    if not expected:
        if required_enabled():
            raise MutationTargetError(
                f"runtime write path requires {IDENTITY_ENV}='<database>|<role>'")
        session.info["eims_identity_status"] = "unconfigured"
        global _unconfigured_warned
        if not _unconfigured_warned:
            _unconfigured_warned = True
            logging.getLogger("eims.db_identity").warning(
                "%s is not configured: runtime identity is NOT verified and the "
                "deployment must not be reported as security-compliant.", IDENTITY_ENV)
        return None
    if expected.count("|") != 1 or not all(part.strip() for part in expected.split("|")):
        raise MutationTargetError(f"malformed {IDENTITY_ENV}; expected '<database>|<role>'")
    had_transaction = session.in_transaction()
    identity = await connection_identity(session)
    if not had_transaction and session.in_transaction():
        # The identity SELECT autobegins a transaction; leaving it open would make
        # a caller's later session.begin() fail. Close only what this check opened.
        await session.rollback()
    if not identity.matches(expected):
        raise MutationTargetError(
            f"runtime connection is {identity.database}|{identity.user}, expected {expected}")
    session.info["eims_identity"] = identity
    session.info["eims_identity_status"] = "verified"
    return identity


async def require_destructive_target(session, *, operation: str) -> ConnectionIdentity:
    """Fail closed unless the live target is trusted or positively disposable.

    Call this on the same session/transaction that will perform the mutation,
    immediately before it; a check on another connection proves nothing.
    """
    try:
        identity = await connection_identity(session)
    except MutationTargetError:
        raise
    except Exception as exc:  # identity unavailable => refuse
        raise MutationTargetError(f"{operation}: cannot verify connection identity ({type(exc).__name__})") from exc

    expected = (os.environ.get(IDENTITY_ENV) or "").strip()
    if expected:
        if not identity.matches(expected):
            raise MutationTargetError(
                f"{operation}: connection is {identity.database}|{identity.user}, "
                f"expected {expected}")
        return identity
    if identity.disposable:
        return identity
    raise MutationTargetError(
        f"{operation}: no {IDENTITY_ENV} configured and target "
        f"{identity.database}|{identity.user} is not marked disposable")
