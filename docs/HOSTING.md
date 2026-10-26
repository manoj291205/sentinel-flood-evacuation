# Hosting the V4 demo

The demo is one container: the built web console plus the FastAPI app. It serves a recorded run of the real engine
(simulated hazards), needs **no API key** and calls **no model**.

**Disclosure rule.** Until P0 is filed the deployment must be private or password-protected (SENTINEL_DEMO_PASSWORD); a public link is switched on only after the user confirms P0 is filed.

## 1. Run it locally

```bash
docker build --build-arg SENTINEL_SOURCE_COMMIT="$(git rev-parse HEAD)" -t sentinel-demo .
docker run -p 8000:8000 -e SENTINEL_DEMO_PASSWORD=choose-one sentinel-demo
```

Open http://127.0.0.1:8000 and sign in with user `sentinel` and your password. `/api/health` needs no password.
The image bakes in no password and no key; `SENTINEL_DEMO_PASSWORD` is set only at run time.

## 2. One free host: Render (web service from the Dockerfile)

Chosen because it builds a Dockerfile directly, injects `PORT` (the image honours it) and keeps secrets in its
dashboard. The free plan sleeps when idle, so the first request after a pause is slow; open the page before a demo.

1. Push the repository to the private GitHub repo and connect it in Render (**New → Web Service**, choose the repo).
2. Runtime: **Docker**; branch: the release branch Lead names; leave build and start commands empty (the Dockerfile has them).
3. Instance type: **Free**.
4. Under **Environment**, add `SENTINEL_DEMO_PASSWORD` as a secret value. Add nothing else; no API key is needed.
5. Deploy. Do not share the URL outside the project while P0 is unfiled; the password is the only guard.
6. After every deploy run the check in section 4.

## 3. Alternative: static console + API container

Build the console (`cd web && npm ci && npm run build`) and put `web/dist` on a static host; run only the API
container elsewhere and point the console at it. Basic auth then protects the API only, so the static files are
public: use this only after the user confirms P0 is filed.

## 4. Check a deployment

```bash
python scripts/deploy_check.py https://<your-host> --password <the password>
```

It runs the checks of `specs/contracts/deploy_check.json` (health, password required, console served, guided demo,
certificates, replay MATCH and tamper MISMATCH, evidence) and exits non-zero if any fails. The password can also come
from `SENTINEL_DEMO_PASSWORD`; it is never printed. Add `--json report.json` to keep the results.
