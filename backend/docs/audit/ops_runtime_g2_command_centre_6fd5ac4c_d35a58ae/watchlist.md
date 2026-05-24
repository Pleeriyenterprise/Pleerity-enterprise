# G2 Command Centre watchlist — 6fd5ac4c_d35a58ae

**Run:** `20260524T170848Z`  
**Classification:** `VERIFIED_OPERATIONALLY`

## Watchlist

- reports endpoint non-200 during cross-reference (G7 not executed; non-blocking)
- Command Centre API latency ~60–65s per bundle fetch on staging (Render cold path)
- CC urgent widget capped at 16 rows (10 urgent + 6 in_progress); Today may list more — documented cap, not island failure
