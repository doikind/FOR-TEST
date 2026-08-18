"""CLI runner for the hot-topic pipeline (stage 1 verification).

Usage:
    python -m cli run              # collect live + run pipeline
    python -m cli snapshot [src]   # collect live and save snapshot(s)
    python -m cli load [src]       # load snapshot(s) and run pipeline

Set PYTHONPATH to include .py-deps if dependencies are bootstrapped there.
"""
import json
import sys

from agents.collectors import orchestrator, snapshot
from core import db
from core.pipeline import run_pipeline


def _print_summary(pipeline_result: dict) -> None:
    print(f"raw={pipeline_result['raw_count']} "
          f"deduped={pipeline_result['deduped_count']} "
          f"removed={pipeline_result['removed_count']}")
    print("-" * 72)
    for i, ev in enumerate(pipeline_result["events"], 1):
        reasons = ev.get("priority_reasons", {})
        fr = reasons.get("follow_reasons", [])
        print(f"{i:2}. [{ev['priority_score']:.3f}] {ev['follow_decision'].upper():8} ({ev['category']}/{ev['source_category']}/{ev['data_authenticity']}) {ev['title'][:70]}")
        print(f"    url={ev['url'][:100]}")
        print(f"    factors: heat={reasons.get('heat')} recency={reasons.get('recency')} category={reasons.get('category')}")
        if fr:
            print(f"    follow: {'; '.join(fr)[:100]}")
        if ev.get("merged_from"):
            print(f"    merged_from={len(ev['merged_from'])} duplicate(s)")


def _save_events_to_db(events: list) -> None:
    db.init_db()
    conn = db.get_conn()
    try:
        for ev in events:
            db.upsert_event(conn, ev)
        conn.commit()
    finally:
        conn.close()


def cmd_run() -> int:
    summary = orchestrator.collect_summary()
    print(f"collected_at={summary['collected_at']} total={summary['total_events']}")
    print(f"by_source={summary['by_source']}")
    for w in summary["warnings"]:
        print(f"[WARN] {w['source']}: {w['reason']}")
    events = summary["events"]
    result = run_pipeline([_ev_from_dict(e) for e in events])
    _print_summary(result)
    return 0


def _ev_from_dict(d: dict):
    from core.models import Event

    return Event.from_dict(d)


def cmd_snapshot(sources: list[str]) -> int:
    from agents.collectors import gdelt, google_news, hacker_news

    collectors = {
        "google_news": google_news.collect,
        "gdelt": gdelt.collect,
        "hacker_news": hacker_news.collect,
    }
    targets = sources or list(collectors.keys())
    for src in targets:
        if src not in collectors:
            print(f"[SKIP] unknown source: {src}")
            continue
        r = collectors[src]()
        path = snapshot.save_snapshot(r.events, src)
        print(f"[SNAPSHOT] {src}: {len(r.events)} events -> {path}")
        for w in r.warnings:
            print(f"[WARN] {w.source}: {w.reason}")
    return 0


def cmd_load(sources: list[str]) -> int:
    available = snapshot.list_snapshots()
    print(f"available snapshots: {available}")
    targets = sources or [s.replace('.json', '') for s in available]
    events = []
    for src in targets:
        try:
            evs = snapshot.load_snapshot(src)
            events.extend(evs)
            print(f"[LOAD] {src}: {len(evs)} events (cached_public)")
        except FileNotFoundError:
            print(f"[MISS] snapshot not found: {src}")
    result = run_pipeline(events)
    _print_summary(result)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    if cmd == "run":
        return cmd_run()
    if cmd == "snapshot":
        return cmd_snapshot(args[1:])
    if cmd == "load":
        return cmd_load(args[1:])
    print(f"unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
