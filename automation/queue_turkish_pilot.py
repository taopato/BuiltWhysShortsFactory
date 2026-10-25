from __future__ import annotations

from control_center_store import ControlCenterStore
from review_queue import DEFAULT_DB


store = ControlCenterStore(DEFAULT_DB)
try:
    row = store.connection.execute(
        """SELECT j.id FROM jobs j WHERE j.language='en-US' AND j.status='approved'
           AND j.policy_status='pass' AND j.quality_status='pass' AND j.human_reviewed=1
           AND NOT EXISTS (SELECT 1 FROM jobs t WHERE t.story_id=j.story_id
                           AND t.language='tr-TR' AND t.status NOT IN ('rejected','failed'))
           ORDER BY j.technical_score DESC,j.updated_at DESC LIMIT 1"""
    ).fetchone()
    if row:
        created = store.create_localization(str(row["id"]), "tr-TR")
        print(created["id"])
    else:
        print("no eligible English source")
finally:
    store.close()
