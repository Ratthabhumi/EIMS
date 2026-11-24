"""RETIRED destructive utility.

This file used to TRUNCATE ``analysis_history`` and ``ai_knowledge`` through the
application database engine with no guard. It is not used by any application,
development, test, setup or deployment workflow, so the capability is retired
rather than re-guarded.

The module is deliberately inert: importing it performs no import of the database
engine, opens no connection and executes no SQL.

If a destructive reset is ever genuinely required, it must run inside a positively
provisioned disposable database prepared by the isolated test-infrastructure
process (see backend/infrastructure/db_identity.py and the handover documents),
never against a working EIMS database.
"""
import sys

RETIRED_MESSAGE = (
    "clear_db.py is retired: it must not truncate application data. "
    "Provision an isolated disposable database for destructive work instead."
)


def main() -> int:
    print(RETIRED_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
