# Deploy and Host Rakazo on Railway

Rakazo is an open-source platform for persistent AI teammates: bots with their
own conversations, memory, routines and history, that you talk to from a web
app. Bring your own model key (OpenRouter, Anthropic, or an OpenAI-compatible
endpoint), and optionally give bots a cloud computer through E2B, Daytona or
Box.

## About Hosting Rakazo

A Rakazo deployment is a long-running api, a background worker, a web UI and
Postgres. This template bundles the api, worker and web UI into one container
because the api and worker share bot files on disk, and Railway attaches a
volume to exactly one service. Postgres runs as a separate Railway service with
its own persistent volume. The container is a thin wrapper over upstream's
published image that fixes volume ownership and boots all three processes with
migrations applied first.

On first boot the container migrates the database, then starts the api, worker
and web UI. That takes about a minute. Every secret the app needs (session
signing, at-rest encryption, screen proxy) is generated for you at deploy time.

## Common Use Cases

- Running a small team of persistent bots that remember context across
  conversations and keep their own notes and artifacts.
- Giving bots scheduled routines and delegated subtasks through the built-in
  worker, without hosting a separate queue.
- Bring-your-own-model agent chat: point the deployment at OpenRouter or any
  OpenAI-compatible endpoint and every call is billed to your key.
- With a sandbox provider key, letting bots open a real desktop: browser,
  terminal and files inside an isolated E2B, Daytona or Box computer.

## Dependencies for Rakazo Hosting

### Deployment Dependencies

- A Railway account. Postgres and all secrets are provisioned by the template.
- Optional: an [OpenRouter](https://openrouter.ai) key, either at deploy time or
  connected in the UI after signup.
- Optional: an [E2B](https://e2b.dev), [Daytona](https://daytona.io) or
  [Box](https://ascii.dev) key if bots should get cloud computers.

### Implementation Details

1. Click deploy. Two services come up: Postgres and Rakazo.
2. Open the Rakazo service's public URL. **The first registered user becomes
   the deployment owner.**
3. Bots can chat once a model is connected. If you did not paste an OpenRouter
   key at deploy time, connect a model in the UI after signup; the app verifies
   the key against the provider before storing it, encrypted.
4. Bot computers are off by default (`SANDBOX_PROVIDER=none`) because Docker
   inside Railway is not possible. To enable desktops, set `SANDBOX_PROVIDER`
   to `e2b`, `daytona` or `box` plus the matching API key variable on the Rakazo
   service, then redeploy.

Signups stay open after the first user. Set `SIGNUPS_ENABLED=false` (or
`SIGNUP_ALLOWLIST`) on the Rakazo service to close the instance.

Troubleshooting:

- **Deploy healthcheck keeps failing**: first boot runs migrations before
  serving; give it two minutes. Past that, read the Rakazo deploy logs: the
  boot script announces each step.
- **403 "Blocked request" in the browser**: `RAKAZO_HOST` must equal the public
  domain. The template wires this; only touch it if you add a custom domain, in
  which case set it to the custom hostname.
- **Never regenerate `ENCRYPTION_KEY`** on an existing deployment: it encrypts
  every stored provider key, and changing it makes them all unreadable.

Upgrades: the image tag is pinned (`v0.1.6`). To move to a newer Rakazo release,
update the Rakazo service's image tag and redeploy. Migrations run on every
boot. Bot conversations and memory live in Postgres; agent homes and artifacts
live on the `/data` volume; both survive redeploys.

## Why Deploy Rakazo on Railway?

Railway runs the whole stack (app, worker, database, persistent storage, TLS,
domains) in one place with no server to operate. The template wires the
database, generates every secret, and applies migrations on boot, so the gap
between clicking deploy and talking to your first bot is about two minutes.
