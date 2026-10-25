"""Explicit auth-only maintenance. Dry run by default; no scheduler installation."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from backend.domain.analyzer.services.session_maintenance import cleanup_auth_records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retention-days',type=int,required=True,help='Owner-approved institutional retention; no universal default')
    parser.add_argument('--batch-size',type=int,default=100)
    parser.add_argument('--apply',action='store_true',help='Commit bounded deletion of eligible auth rows; otherwise preview only')
    args=parser.parse_args()
    raw=os.environ.get('EIMS_MAINTENANCE_DATABASE_URL','')
    if not raw or args.retention_days<1 or not 1<=args.batch_size<=1000:
        parser.error('Explicit maintenance DB URL, retention >=1 day and batch 1..1000 required')
    url=make_url(raw)
    if url.drivername!='postgresql+asyncpg':
        parser.error('PostgreSQL asyncpg URL required')
    async def run():
        engine=create_async_engine(url)
        try:
            async with AsyncSession(engine) as session:
                counts=await cleanup_auth_records(session,retention_seconds=args.retention_days*86400,
                    batch_size=args.batch_size,dry_run=not args.apply)
            print(json.dumps({'dry_run':not args.apply,'counts':counts}))
        finally:
            await engine.dispose()
    try:
        asyncio.run(run())
    except Exception:
        parser.exit(1,'Maintenance failed; transaction rolled back. Check local configuration without exporting credentials.\n')


if __name__=='__main__':
    main()
