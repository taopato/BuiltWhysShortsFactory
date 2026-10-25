from __future__ import annotations

import time

from automation.control_center_api import _sign


print(_sign({"kind": "session", "email": "audit-evidence", "exp": int(time.time()) + 900}))
