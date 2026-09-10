# Rakazo on Railway

One-click Railway template for [Rakazo](https://github.com/elie222/rakazo) -
persistent AI teammates with their own conversations, memory, routines, and
optional cloud computers.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/rakazo)

## What you get

- **Rakazo** - one container running the api, the Graphile worker, and the web
  UI (vite preview). Built from `ghcr.io/hmseeb/rakazo-railway`, a thin wrapper
  over upstream's `ghcr.io/elie222/rakazo/app:v0.1.6` that fixes Railway volume
  ownership and boots the three processes together.
- **Postgres** - Railway's postgres-ssl image with a persistent volume.

## After deploy

1. Open the public URL. The **first registered user becomes the deployment
   owner**.
2. Bots can chat immediately once a model is connected. Either paste an
   OpenRouter key at deploy time or connect a model in the UI after signup.
3. Bot computers are **off by default** (`SANDBOX_PROVIDER=none`) because
   Docker-in-Railway is not possible. To give bots a desktop, set
   `SANDBOX_PROVIDER` to `e2b`, `daytona` or `box` and the matching API key
   variable, then redeploy.

## Notes

- Signups stay open after the first user. Set `SIGNUPS_ENABLED=false` (or
  `SIGNUP_ALLOWLIST`) on the Rakazo service to close the instance.
- `ENCRYPTION_KEY` encrypts stored provider credentials. Never regenerate it on
  an existing deployment - every saved key becomes unreadable.
- `/data` (agent homes, artifacts, sessions) is on a persistent volume.

## Repository layout

- `image/` - the wrapper Dockerfile and boot script
- `test/contract.sh` - contract test for the wrapper image
- `template.json` - build sheet a future session reads to regenerate
- `build_source.py` - rebuilds the live source project in the Auromations workspace
