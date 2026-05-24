# G0 Programme Precheck — 6fd5ac4c_d35a58ae

**Run:** `20260524T140328Z`

**Classification:** `CONTROL_PLANE_CIRCULARITY`

**Reasons:** unresolved_control_plane_cycles, deploy_sha_ambiguous

**Secondary:** COGNITIVE_TRUST_RISK, deploy_sha_ambiguous

**Note:** 7 static-graph cycles with `resolution_reachable=false` (e.g. documents↔requirements, property↔today); 4 unresolved aggregate escalation chains; runtime surfaces all reachable.

Read-only G0 execution; no lifecycle mutations.
