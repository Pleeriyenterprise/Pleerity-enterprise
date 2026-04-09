# Render backend: port scan timeout – diagnosis

## 1. Startup path before Uvicorn binds

Uvicorn/Starlette **do not open the port until lifespan startup completes**. So any code that runs in `lifespan(app)` before `yield` must finish without raising or blocking, or the process never listens and Render sees "no open ports".

**Order in `server.py` lifespan:**

| Step | Location | Can block/raise? |
|------|----------|------------------|
| 1 | `PYTEST_RUNNING == "1"` → yield & return | No (early exit) |
| 2 | `ENVIRONMENT` in (`production`, `prod`) | No |
| 3 | **`require_non_default_jwt_secret()`** | **Yes – raises RuntimeError** if JWT_SECRET missing/default |
| 4 | **`validate_url_configuration()`** | **Yes – raises RuntimeError** on conflicting origins or non-HTTPS app URL |
| 5 | `_render_defer` check, `_heavy_startup()`, yield | No raise (defer path only schedules a task then yields). Defer runs when `RENDER` is true/1/yes **or** `RENDER_SERVICE_ID` is set (Render always sets the latter). |

So **steps 3 and 4 run before we ever reach the RENDER-defer logic**. If either raises, lifespan never reaches `yield` → port never opens → "Port scan timeout reached".

## 2. URL validation and recent changes

- **File:** `backend/utils/app_urls.py`
- **Function:** `validate_url_configuration()`

**When it runs:** Only when `ENVIRONMENT` (or `ENV`) is `production` or `prod`. Skipped if `PYTEST_RUNNING=1` or `SKIP_URL_VALIDATION` is set.

**When it raises:**

1. **Multiple distinct app origins:** More than one of  
   `APP_BASE_URL`, `FRONTEND_PUBLIC_URL`, `FRONTEND_URL`, `PUBLIC_APP_URL`, `PORTAL_BASE_URL`  
   is set and they normalize to different origins (e.g. different hosts, or before normalization different schemes on same host could have caused this; normalization was added so http/https same host no longer conflicts).

2. **Non-HTTPS app URL:** `get_app_base_url(for_email_links=True)` returns a non-localhost URL that does not start with `https://`.

So invalid or inconsistent URL config in production **will** prevent the server from ever binding.

## 3. Render start command / PORT

- Repo has no `render.yaml`; the start command is configured in the Render dashboard.
- README suggests: `uvicorn server:app --host 0.0.0.0 --port 8001` (or "Render's default").
- Render sets **`PORT`** (e.g. 10000). The process **must** listen on `0.0.0.0:$PORT`. If the start command uses a fixed port (e.g. 8001), Render’s port scan may still fail because it checks the port it assigned (`$PORT`).
- **Action:** In Render, set the start command to use `$PORT`, e.g.:  
  `uvicorn server:app --host 0.0.0.0 --port $PORT`  
  (or `gunicorn` with a uvicorn worker and `--bind 0.0.0.0:$PORT`).

## 4. Likely failure point

**Most likely:** **`backend/utils/app_urls.py` → `validate_url_configuration()`** raising `RuntimeError` in production because:

- At least two app URL env vars are set to **different hosts** (e.g. one to `https://pleerityenterprise.co.uk`, another to a staging or www variant with a different host), or  
- The resolved app URL is not HTTPS (e.g. typo, missing scheme, or env not set and fallback is wrong).

**Second possibility:** **`backend/auth.py` → `require_non_default_jwt_secret()`** raising if `JWT_SECRET` is unset or still the default in production.

In both cases the process exits before `yield` → no port is ever opened.

## 5. Safest fix so invalid URL config doesn’t silently break startup

- **Do not** silently ignore URL problems: keep validation and make failures visible.
- **Do** ensure the Render process **always reaches `yield`** so the port binds, then surface URL (and JWT) issues via logs and optional health.

**Recommended approach:**

- **On Render only:** In production, if URL validation would raise, **log at CRITICAL and continue** instead of raising. The app will bind and start; invalid URL config will still be obvious in logs and can be fixed in env. Optionally set `app.state.url_config_invalid = True` and have `/api/health` reflect that (e.g. 503 or a warning field).
- **JWT:** Keep **fail-hard** at startup (do not relax for Render); missing/default JWT is a security risk and should prevent the app from serving traffic.
- **Start command:** Use `$PORT` on Render as above.

## 6. How to handle validation: fail hard vs warn vs staged

| Option | Pros | Cons |
|--------|------|------|
| **Fail hard at startup** | Clear, no bad config in production | Any validation failure → no port → Render timeout; hard to distinguish from other startup failures. |
| **Warn and continue** | Port always opens; misconfig visible in logs; deploy succeeds. | Invalid URL config can go live until someone checks logs or health. |
| **Staged on Render** | Port opens; validation can run in background or on first request; health can report "config invalid". | More code paths and complexity. |

**Recommendation:**

- **Default (non-Render):** Keep **fail hard** in production so invalid URL config is caught at deploy time.
- **On Render:** Use **warn and continue** for URL validation only: on `RENDER=true`, if validation would raise, **log CRITICAL with the same message and return** instead of raising. That way:
  - Invalid URL config does not silently break production startup; it is logged and the service still binds.
  - You do not need to "temporarily disable" validation; you only soften the failure mode on Render so the process can open the port and you can fix env from logs.

**Temporarily disabling strict validation:** You can set **`SKIP_URL_VALIDATION=true`** in Render env as an emergency escape so the app always passes URL validation and binds. Prefer the **warn-on-Render** change so you keep validation and visibility without blocking the port.

---

## Exact fix to make Render boot successfully

1. **Code:** In `backend/utils/app_urls.py`, inside `validate_url_configuration()`, when in production and running on Render (`RENDER=true`), if you would raise either RuntimeError (conflicting origins or non-HTTPS), **log the same message at CRITICAL and return** instead of raising. Everywhere else (non-Render production), keep raising as today.

2. **Config:** In Render dashboard, set the backend start command to use **`$PORT`**, e.g.  
   `uvicorn server:app --host 0.0.0.0 --port $PORT`.

3. **JWT:** Ensure **`JWT_SECRET`** is set in Render to a non-default value; otherwise the process will still abort before binding.

4. **Optional:** Use **`SKIP_URL_VALIDATION=true`** only as a temporary workaround if you need to unblock a deploy before applying the code change; then remove it and rely on the warn-on-Render behavior.
