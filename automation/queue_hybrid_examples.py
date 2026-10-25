from __future__ import annotations

import argparse
import json
from pathlib import Path

from control_center_store import ControlCenterStore
from review_queue import DEFAULT_DB, utc_now


EXAMPLES = (
    "Why plastic soda bottles have five feet on the bottom",
    "Why bridges have expansion joints",
    "Why seat belts lock during a sudden pull",
)

PACKAGES = {
    EXAMPLES[0]: {
        "title": "Why Soda Bottles Have Five Feet",
        "cover": "BUILT TO HOLD PRESSURE",
        "script": "That five-footed shape under a soda bottle is doing more than keeping it upright. Carbon dioxide pushes on every part of the thin PET shell, including the bottom. A broad, flat base could flex outward under that internal pressure, making the bottle rock or tip. The petaloid base replaces one flexible panel with curved valleys and several reinforced feet. Those curves make the base stiffer, while the feet create stable contact points on the table. The result is a lightweight, one-piece bottle that can stand by itself while resisting pressure with less plastic.",
        "queries": ["carbonated soda bottle close up", "plastic soda bottle bottom macro", "PET bottle manufacturing", "carbonated drink bubbles bottle", "plastic bottle factory conveyor", "soda bottle standing on table"],
        "caption": "The flower-like base of a carbonated PET bottle is called a petaloid base. Its curved valleys and feet help a thin, lightweight bottle remain self-standing while resisting internal pressure.",
        "hashtags": ["#Engineering", "#Design", "#PETBottle", "#HowItWorks", "#BuiltWhys"],
        "sources": ["https://patents.google.com/patent/EP2555984B1/en", "https://patents.google.com/patent/US5850932A"],
    },
    EXAMPLES[1]: {
        "title": "Why Bridges Need Expansion Joints",
        "cover": "BRIDGES HAVE TO MOVE",
        "script": "A bridge may look rigid, but its deck is constantly changing length. Sunlight warms the steel and concrete, so the structure expands; cooler temperatures make it contract. If both ends were locked in place, that movement would build stress, crack surfaces, or push against the supports. Expansion joints create a controlled gap between deck sections. Their interlocking parts keep the driving surface usable while allowing the gap to open and close as temperature changes. The movement is small compared with the bridge, but managing it is what keeps a solid structure from fighting its own materials.",
        "queries": ["bridge expansion joint close up", "car crossing bridge road", "steel bridge deck detail", "bridge maintenance worker", "bridge joint road macro", "traffic crossing modern bridge"],
        "caption": "Bridge decks expand when warm and contract when cool. Expansion joints provide a controlled place for that thermal movement while keeping the roadway connected.",
        "hashtags": ["#Engineering", "#Bridges", "#Infrastructure", "#HowItWorks", "#BuiltWhys"],
        "sources": ["https://www.fhwa.dot.gov/bridge/pubs/hif17019.pdf", "https://www.fhwa.dot.gov/bridge/steel/pubs/nhi16016.pdf"],
    },
    EXAMPLES[2]: {
        "title": "Why Seat Belts Lock When Pulled Fast",
        "cover": "SPEED TRIGGERS THE LOCK",
        "script": "Pull a seat belt slowly and the spool turns freely. Yank it, and the same belt stops almost instantly. Inside the retractor, the belt winds around a toothed spool. During normal movement, the spool can rotate as you lean forward. A sudden pull makes the spool accelerate quickly, activating a small locking mechanism. A pawl then catches the teeth and prevents more webbing from leaving the retractor. Release the tension and the mechanism resets. The belt is not sensing danger like a computer; its mechanical response turns the speed of the pull into a physical lock.",
        "queries": ["car seat belt close up", "person pulling seat belt", "seat belt buckle car interior", "seat belt retractor mechanism", "car safety belt detail", "driver fastening seat belt"],
        "caption": "A seat-belt retractor allows slow movement but locks during a rapid pull. Its mechanical parts convert sudden spool acceleration into a physical stop.",
        "hashtags": ["#Engineering", "#SeatBelt", "#CarSafety", "#HowItWorks", "#BuiltWhys"],
        "sources": ["https://static.nhtsa.gov/odi/tsbs/2013/MC-10134736-9999.pdf", "https://static.nhtsa.gov/odi/tsbs/2012/SB-10046159-5054.pdf"],
    },
}


def queue_examples(store: ControlCenterStore, limit: int) -> list[dict]:
    queued: list[dict] = []
    for topic in EXAMPLES[:limit]:
        existing = store.connection.execute(
            """SELECT id,title,status FROM jobs WHERE topic=?
               AND status!='rejected' ORDER BY created_at DESC LIMIT 1""",
            (topic,),
        ).fetchone()
        if existing:
            queued.append({**dict(existing), "created": False})
            continue
        job = store.queue.create_job(topic, topic, "")
        note = (
            "Create a token-free hybrid edit: open with real Pexels footage, explain the "
            "mechanism with the matching original procedural animation, and resolve with real footage."
        )
        store.update_job(job["id"], {
            "revision_note": note,
            "channel_key": "builtwhys",
            "language": "en-US",
            "platforms": "youtube,instagram,facebook",
            "candidate_score": 95,
        })
        store.connection.execute(
            """UPDATE jobs SET status='revision_requested',review_action='hybrid',
               decision_note=?,updated_at=? WHERE id=?""",
            (note, utc_now(), job["id"]),
        )
        store.connection.commit()
        store.event("info", "hybrid_example_queued", topic, job["id"], generation="pexels+procedural")
        queued.append({"id": job["id"], "title": topic, "status": "revision_requested", "created": True})
    return queued


def seed_examples(store: ControlCenterStore) -> list[dict]:
    from producer_worker import PILOTS, diagram

    seeded = []
    for topic, package in PACKAGES.items():
        row = store.connection.execute(
            """SELECT * FROM jobs WHERE topic=? AND revision_note LIKE 'Create a token-free hybrid edit:%'
               AND status!='rejected' ORDER BY created_at LIMIT 1""", (topic,),
        ).fetchone()
        if not row:
            continue
        job = dict(row)
        pilot = PILOTS / f"generated-{job['id']}"
        pilot.mkdir(parents=True, exist_ok=True)
        (pilot / "script.txt").write_text(package["script"] + "\n", encoding="utf-8")
        (pilot / "cover.txt").write_text(package["cover"] + "\n", encoding="utf-8")
        (pilot / "pexels_queries.json").write_text(
            json.dumps(package["queries"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        (pilot / "shot_plan.json").write_text(json.dumps({
            "title": package["title"], "cover_text": package["cover"], "language": "en-US",
            "format": "Pexels + original procedural mechanism + Pexels",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (pilot / "social_metadata.json").write_text(json.dumps({
            "language": "en-US", "caption": package["caption"], "hashtags": package["hashtags"],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assets = pilot / "assets"
        assets.mkdir(exist_ok=True)
        diagram(assets / "scene-01-hero.png", package["title"], "REAL OBJECT, HIDDEN MECHANISM", 1)
        diagram(assets / "scene-02-mechanism.png", "MECHANISM", "FOLLOW THE LOAD AND MOVEMENT", 1)
        diagram(assets / "scene-03-result.png", "RESULT", "THE SHAPE CONTROLS THE FORCE", 2)
        (pilot / "manifest.json").write_text(json.dumps({
            "job_id": job["id"], "ai_disclosure_required": False,
            "fact_sources": [{"title": "Primary engineering reference", "publisher": "Patent or public safety/transport authority", "url": url, "accessed_at": utc_now()[:10]} for url in package["sources"]],
            "assets": [{"type": "procedural_diagram", "source_url": f"local://{path.relative_to(Path(__file__).resolve().parents[1]).as_posix()}", "license": "Project-generated original diagram", "commercial_use": True} for path in sorted(assets.glob("scene-*.png"))],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        store.update_job(job["id"], {
            "pilot_dir": str(pilot), "title": package["title"], "script": package["script"],
            "description": package["caption"], "hashtags": " ".join(package["hashtags"]),
        })
        store.connection.execute(
            """UPDATE jobs SET status='revision_requested',review_action='hybrid',decision_note=?,updated_at=?
               WHERE id=?""",
            (job["revision_note"], utc_now(), job["id"]),
        )
        store.connection.commit()
        seeded.append({"id": job["id"], "topic": topic, "pilot": str(pilot)})
    return seeded


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue token-free BuiltWhys hybrid examples.")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int, default=3, choices=(1, 2, 3))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--purge-duplicates", action="store_true")
    parser.add_argument("--link-bottle-revision", action="store_true")
    parser.add_argument("--refresh-hybrids", action="store_true")
    parser.add_argument("--repair-hybrid-visual-revisions", action="store_true")
    args = parser.parse_args()
    store = ControlCenterStore(args.db)
    try:
        if args.repair_hybrid_visual_revisions:
            rows = store.connection.execute(
                """SELECT child.* FROM jobs child JOIN jobs parent ON parent.id=child.parent_job_id
                   WHERE child.review_action='' AND child.revision_note<>''
                   AND child.revision_note NOT LIKE 'Create a token-free hybrid edit:%'
                   AND child.status='pending_review' ORDER BY child.created_at DESC"""
            ).fetchall()
            result = []
            for row in rows:
                job = dict(row)
                parent = store.queue.get_job(job["parent_job_id"])
                try:
                    parent_manifest = json.loads(Path(parent["manifest_path"]).read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    parent_manifest = {}
                if not parent_manifest.get("hybrid_template"):
                    continue
                pilot = Path(job["pilot_dir"])
                manifest_path = pilot / "manifest-v3.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["hybrid_template"] = parent_manifest["hybrid_template"]
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                store.connection.execute(
                    """UPDATE jobs SET status='revision_requested',review_action='visuals',
                       decision_note=?,updated_at=? WHERE id=?""",
                    (job["revision_note"], utc_now(), job["id"]),
                )
                store.connection.commit()
                result.append({"id": job["id"], "note": job["revision_note"], "hybrid_template": parent_manifest["hybrid_template"]})
        elif args.refresh_hybrids:
            rows = store.connection.execute(
                """SELECT id FROM jobs WHERE revision_note LIKE 'Create a token-free hybrid edit:%'
                   AND status IN ('pending_review','approved','held')"""
            ).fetchall()
            result = []
            for row in rows:
                job_id = str(row["id"])
                result.append({
                    "id": job_id,
                    "policy": store.refresh_policy(job_id),
                    "quality": store.refresh_quality(job_id),
                })
        elif args.link_bottle_revision:
            topic = EXAMPLES[0]
            hybrid = store.connection.execute(
                """SELECT * FROM jobs WHERE topic=? AND revision_note LIKE 'Create a token-free hybrid edit:%'
                   AND status!='rejected' ORDER BY created_at LIMIT 1""", (topic,),
            ).fetchone()
            prior = store.connection.execute(
                """SELECT * FROM jobs WHERE topic=? AND id<>? AND status NOT IN ('rejected','failed')
                   ORDER BY version DESC,created_at DESC LIMIT 1""",
                (topic, str(hybrid["id"]) if hybrid else ""),
            ).fetchone()
            if not hybrid or not prior:
                result = {"linked": False, "reason": "hybrid or prior version not found"}
            else:
                story_id = str(prior["story_id"] or prior["id"])
                store.connection.execute(
                    """UPDATE jobs SET parent_job_id=?,story_id=?,version=?,updated_at=? WHERE id=?""",
                    (prior["id"], story_id, int(prior["version"] or 1) + 1, utc_now(), hybrid["id"]),
                )
                if prior["status"] in {"pending_review", "approved"}:
                    store.connection.execute(
                        """UPDATE jobs SET status='held',is_reserve=0,decision_note=?,updated_at=? WHERE id=?""",
                        (f"Superseded by hybrid revision {hybrid['id']}", utc_now(), prior["id"]),
                    )
                    store.connection.execute(
                        "UPDATE schedule_entries SET job_id='',source='default',updated_at=? WHERE job_id=? AND status='planned'",
                        (utc_now(), prior["id"]),
                    )
                store.connection.commit()
                result = {"linked": True, "hybrid": hybrid["id"], "parent": prior["id"], "story_id": story_id}
        elif args.purge_duplicates:
            rows = store.connection.execute(
                "SELECT id FROM jobs WHERE decision_note LIKE 'Duplicate hybrid example; canonical job is %'"
            ).fetchall()
            ids = [str(row["id"]) for row in rows]
            for job_id in ids:
                for table in ("events", "schedule_entries", "publications", "analytics_snapshots"):
                    store.connection.execute(f"DELETE FROM {table} WHERE job_id=?", (job_id,))
                store.connection.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            store.connection.commit()
            result = {"purged_duplicate_jobs": ids}
        elif args.seed:
            result = seed_examples(store)
        elif args.repair:
            repaired = []
            for topic in EXAMPLES:
                rows = store.connection.execute(
                    """SELECT id FROM jobs WHERE topic=? AND revision_note LIKE 'Create a token-free hybrid edit:%'
                       AND status!='rejected' ORDER BY created_at""", (topic,),
                ).fetchall()
                if not rows:
                    continue
                keep = str(rows[0]["id"])
                store.connection.execute(
                    "UPDATE jobs SET status='revision_requested',review_action='hybrid',updated_at=? WHERE id=?",
                    (utc_now(), keep),
                )
                for row in rows[1:]:
                    store.connection.execute(
                        """UPDATE jobs SET status='rejected',review_action='',decision_note=?,updated_at=?
                           WHERE id=?""",
                        (f"Duplicate hybrid example; canonical job is {keep}", utc_now(), row["id"]),
                    )
                repaired.append({"topic": topic, "kept": keep, "duplicates_rejected": max(0, len(rows) - 1)})
            store.connection.commit()
            result = repaired
        elif args.list:
            rows = store.connection.execute(
                """SELECT id,topic,status,review_action,version,revision_note,decision_note,updated_at
                   FROM jobs WHERE topic IN (?,?,?) ORDER BY created_at DESC""",
                EXAMPLES,
            ).fetchall()
            result = [dict(row) for row in rows]
        else:
            result = queue_examples(store, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
