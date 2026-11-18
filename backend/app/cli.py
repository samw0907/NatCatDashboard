# backend/app/cli.py
#
# Local data operations without going through the HTTP API. Uses whatever
# database the local .env points at (currently Railway production), so
# every command here writes to real data - run from a local machine only,
# never from a cloud session. Run from backend/:
#
#   python -m app.cli ingest usgs --score-limit 0
#   python -m app.cli score nifc --limit 20
#   python -m app.cli prune              (dry run, deletes nothing)
#   python -m app.cli prune --execute    (deletes - review the dry run first)

import argparse
import json

from . import gdacs, nhc, nifc, pruning, usgs
from .db import get_session


def ingest(source: str, score_limit: int) -> dict:
    with get_session() as db:
        if source == "usgs":
            result = usgs.upsert_events(db, usgs.fetch_summary())
            result["normalized"] = usgs.normalize_to_events(db)
            result["economic_scoring"] = usgs.score_economic(db, limit=score_limit)
        elif source == "nifc":
            result = nifc.upsert_events(db, nifc.fetch_perimeters())
            result["normalized"] = nifc.normalize_to_events(db)
            result["scoring"] = nifc.score_events(db, limit=score_limit)
        elif source == "nhc":
            result = nhc.upsert_storms(db, nhc.fetch_current_storms())
            result["normalized"] = nhc.normalize_to_events(db)
            result["scoring"] = nhc.score_events(db, limit=score_limit)
            result["rss"] = nhc.upsert_rss_items(db, nhc.fetch_rss_items())
        else:
            result = gdacs.upsert_events(db, gdacs.fetch_events())
    return result


def score(source: str, limit: int) -> dict:
    scorers = {"usgs": usgs.score_economic, "nifc": nifc.score_events, "nhc": nhc.score_events}
    with get_session() as db:
        return scorers[source](db, limit=limit)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="fetch, store, normalise and score one source")
    p_ingest.add_argument("source", choices=["usgs", "nifc", "nhc", "gdacs", "all"])
    p_ingest.add_argument("--score-limit", type=int, default=20)

    p_score = sub.add_parser("score", help="run only the expensive NSI scoring pass")
    p_score.add_argument("source", choices=["usgs", "nifc", "nhc"])
    p_score.add_argument("--limit", type=int, default=20)

    p_prune = sub.add_parser("prune", help="rolling-window pruning, dry run unless --execute")
    p_prune.add_argument("--execute", action="store_true", help="actually delete rows")

    args = parser.parse_args()

    if args.command == "ingest":
        sources = ["usgs", "nifc", "nhc", "gdacs"] if args.source == "all" else [args.source]
        output = {s: ingest(s, args.score_limit) for s in sources}
    elif args.command == "score":
        output = score(args.source, args.limit)
    else:
        with get_session() as db:
            output = pruning.prune_all(db, dry_run=not args.execute)

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
