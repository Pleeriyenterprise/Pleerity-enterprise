# Investigation: Scheduler Execution vs Job-Run Observability Gap

**Scenario:** A scheduled job was observed running at its actual scheduled time, and APScheduler advanced its `next_run_time`, but no corresponding run appeared in the Automation Control Centre.

This document traces the exact execution path, database usage, and UI data flow so the gap can be identified with evidence.

---

## 1. Execution path (APScheduler → job_runs)

| Step | Location | What happens |
|------|----------|--------------|
| 1 | `server.py` | Scheduler is created with MongoDB job store: `MongoDBJobStore(database=db_name, collection='scheduled_jobs', client=MongoClient(mongo_url))`. `db_name` = `os.environ.get('DB_NAME', 'compliance_vault_pro')` at **module load**. |
| 2 | `server.py` lifespan | `await database.connect()` → Motor `AsyncIOMotorClient(mongo_url)` from `os.environ['MONGO_URL']`, `database.db = client[os.environ['DB_NAME']]`. |
| 3 | `server.py` lifespan | `scheduler.add_job("job_runner:run_scheduled_job", ..., args=[job_id], kwargs={"run_type": "schedule"})` for every job. **Callable is the string** `"job_runner:run_scheduled_job"`, not a function reference (so it can be pickled in MongoDB). |
| 4 | APScheduler (at trigger time) | Resolves `job_runner:run_scheduled_job` and invokes `run_scheduled_job(job_id, run_type="schedule")` with `job_id` from `args`. |
| 5 | `job_runner.run_scheduled_job` | Calls `run_instrumented(job_id, run_type, triggered_by=None)`. |
| 6 | `job_runner.run_instrumented` | Gets `fn = JOB_RUNNERS.get(job_id)`. If `job_id` is not in `JOB_RUNNERS`, raises `ValueError("Unknown job_id: ...")` **before** `start_job_run`. Then calls `job_run_id = await start_job_run(job_id, run_type, triggered_by=triggered_by)`. |
| 7 | `services/job_run_service.start_job_run` | `db = database.get_db()`. Inserts into `db[COLLECTION]` where `COLLECTION = "job_runs"`. Returns `str(result.inserted_id)`. |
| 8 | `job_runner.run_instrumented` | Runs `await fn()`. On success/failure/degraded calls `finish_job_run_success` / `finish_job_run_failure` / `finish_job_run_degraded` with `job_run_id`. |

**Conclusion:** The only way a run can execute (and APScheduler advance `next_run_time`) without a row in `job_runs` is:

- **a)** Exception **before** `start_job_run` (e.g. unknown `job_id` → `JOB_RUNNERS.get(job_id)` is None). The job would raise; scheduler still advances next run.
- **b)** `database.get_db()` returned `None` (e.g. scheduler runs in a process that never called `database.connect()`). Then `db[COLLECTION].insert_one(doc)` would raise `AttributeError`. Job would crash.
- **c)** `start_job_run` wrote to a **different database** than the one the admin UI reads from (e.g. different `DB_NAME` in the process that runs jobs vs the one serving the API, or typo in one place).
- **d)** Row was written but the **UI/API does not show it** (wrong collection, filter, or frontend key).

---

## 2. Scheduler callable confirmation

| Item | Value |
|------|--------|
| Registered callable | `"job_runner:run_scheduled_job"` (string ref for all jobs in `server.py`) |
| Args | `args=[job_id]` e.g. `["daily_reminders"]` |
| Kwargs | `kwargs={"run_type": "schedule"}` |

So the live scheduler **does** use `run_scheduled_job` for every job. There is no alternate code path that bypasses instrumentation.

---

## 3. Database and collection usage

| Consumer | Database name | Collection | When |
|----------|----------------|------------|------|
| **Scheduler persistence** (APScheduler job store) | `os.environ.get('DB_NAME', 'compliance_vault_pro')` at server.py **import** | `scheduled_jobs` | PyMongo `MongoClient(mongo_url)` |
| **start_job_run / finish_job_run_*** | `database.get_db()` → `database.db` set in `database.connect()` using `os.environ['DB_NAME']` | `job_runs` | Motor (async), same process after lifespan |
| **Observability routes** (`get_job_runs`, `get_health_summary`) | `database.get_db()` | `job_runs` | Same singleton as job_run_service |
| **Automation Centre UI** | Via API: `GET /api/admin/observability/job-runs?limit=200` and `GET /api/admin/observability/health-summary` | — | Reads from same backend |

**Critical:** Scheduler jobstore uses **PyMongo** and reads `MONGO_URL`/`DB_NAME` at **import**. App uses **Motor** and reads them in **lifespan** (`database.connect()`). If the process is the same, both use the same env; if `DB_NAME` or `MONGO_URL` differ between import and connect (e.g. env changed), scheduler and app could point to different DBs. In normal single-process deployment they match.

---

## 4. Automation Control Centre – query and filters

| Source | API | Collection | Filters | Sort | Limit |
|--------|-----|------------|---------|------|--------|
| Job list (table rows) | `GET /api/admin/jobs/status` | — | — | — | All scheduler jobs |
| Run data (last run, status) | `GET /api/admin/observability/job-runs` | `job_runs` | None by default (optional `job_name`, `status`) | `created_at` desc | 200 |
| Health / state per job | `GET /api/admin/observability/health-summary` | `job_runs`, `scheduler_heartbeat`, `incidents` | Per `HEALTH_SUMMARY_JOBS` (same 14 as registry) | — | — |

- **jobIds** in the UI = union of (1) `Object.keys(byJob)` (job names that appear in the 200 job_runs items) and (2) `scheduled_jobs` ids from `/admin/jobs/status`. So every scheduled job gets a row; “last run” comes from `job_runs` only.
- **No** time window filter on the job-runs list (only sort by `created_at` desc and limit 200).
- **No** `run_type` filter; schedule and manual runs both appear.

So if a run exists in `job_runs` with the correct `job_name`, it will appear in the Automation Centre (either in the 200 fetched, or as the “last run” for that job if it’s the most recent for that name).

---

## 5. Which of (a)–(d) is true?

| Hypothesis | How to confirm |
|------------|----------------|
| **a) Job executed but bypassed instrumentation** | Code shows no bypass: all scheduler jobs use `run_scheduled_job` → `run_instrumented` → `start_job_run`. If `job_id` not in `JOB_RUNNERS`, job raises **before** `start_job_run`; next_run_time still advances. Check logs for `ValueError: Unknown job_id`. |
| **b) job_runs row exists but UI does not show it** | Query `job_runs` immediately after the scheduled run: `db.job_runs.find({"job_name": "<job_id>"}).sort("created_at", -1).limit(5)`. If a row exists with `started_at` at the run time, the UI should show it (same DB, no filter by run_type). Check that UI uses `job_name` from API (no case/format mismatch). |
| **c) job_runs written to different DB/environment** | Ensure single process: only one process runs the scheduler and serves the API, and that process called `database.connect()` in lifespan. If multiple processes, the one that runs jobs must call `database.connect()` with the same `MONGO_URL`/`DB_NAME`. Add logging: in `start_job_run` log the DB name (e.g. `db.name`) at INFO so logs show which DB received the insert. |
| **d) start_job_run / finish_job_run failing silently** | `start_job_run` does not catch `insert_one`; it would raise. `finish_job_run_*` can “silently” skip update if run not found (logs warning). If `start_job_run` succeeds but `finish_job_run_*` never runs (e.g. job crashes in `fn()` before finish), the row exists with `status: "running"`. So “no row at all” implies `start_job_run` either never ran or raised. Check logs for `job_run started job_name=...` (DEBUG) or any exception before it. |

---

## 6. Exact evidence to gather

1. **Scheduler callable**  
   In running process:  
   `from server import scheduler; [ (j.id, j.func_ref) for j in scheduler.get_jobs() ][:3]`  
   Expect: `func_ref` resolving to `run_scheduled_job`.

2. **DB names**  
   - Scheduler: from `server.py`, at import: `db_name = os.environ.get('DB_NAME', 'compliance_vault_pro')`.  
   - App: from `database.db` after connect: same as `os.environ['DB_NAME']` in that process.  
   Add to health-summary or a small debug: return `observability_db_name: database.get_db().name` (or equivalent) so the UI/config can confirm which DB the API uses.

3. **Sample job_runs query (after a scheduled run)**  
   In MongoDB shell or script:  
   `db.job_runs.find({"job_name": "scheduler_heartbeat"}).sort({created_at: -1}).limit(3)`  
   (Replace with the job_id that was observed running.)  
   Confirm: a document with `started_at` at the run time exists and has the expected `job_name`.

4. **Sample admin query**  
   Call `GET /api/admin/observability/job-runs?job_name=<job_id>&limit=10`.  
   Confirm: response includes the run that just executed (same `started_at` / `created_at`).

5. **Root cause**  
   - If the document **exists** in MongoDB for that job/time but **not** in the API response: wrong DB or wrong collection in the API (or different process with different DB).  
   - If the document **does not exist**: either `start_job_run` was never called (exception before it, or wrong process) or it wrote to another DB; then check logs and DB name in the process that runs the scheduler.

---

## 7. Recommended code changes (already or to add)

- **Defensive check in `start_job_run`:** If `db is None`, raise a clear exception (e.g. `RuntimeError("Database not connected; cannot record job run. Ensure database.connect() was called in this process.")`). Prevents silent no-op and makes multi-process misconfiguration obvious.
- **INFO logging in `run_instrumented`:** Log once before `start_job_run(job_id, ...)` and once after with `job_run_id`, so that “job ran but no row” can be correlated with “did we call start_job_run and get an id?”.
- **Observability response:** Include in health-summary (or a debug endpoint) the database name used for `job_runs` so operators can confirm the API and the job-run writer use the same DB.

These are implemented in the codebase:

- **job_run_service.start_job_run:** If `database.get_db()` is `None`, raises `RuntimeError` with a clear message. Logs at INFO: `job_run started job_name=... job_run_id=... run_type=... db=<db_name>` so the DB used for the insert is visible in logs.
- **job_runner.run_instrumented:** Logs at INFO before and after `start_job_run`; logs at ERROR if `job_id` is not in `JOB_RUNNERS` (so "unknown job_id" is visible).
- **GET /api/admin/observability/health-summary:** Response includes `observability_db_name` (the name of the database used for `job_runs`). Compare with the DB name in the `job_run started ... db=...` log line to confirm scheduler and API use the same DB.
