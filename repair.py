#!/usr/bin/env python3
"""Puts back everything templateGenerate strips.

Generation drops every literal variable value as an anti-secret measure, so what
comes out is the right shape with nothing in it. This writes the real config
through templateUpsertConfig on the internal endpoint (the composer's own Save
button), then reads it back and checks it field by field. All four input fields
are required or it fails with a generic error.

What templateGenerate hands back cannot be edited: passing its id to
templateUpsertConfig returns "Not Authorized". So generation is treated as a
read: its config is copied into a fresh template, with a fresh UUID for the
template and for every service and volume inside it, because the server rejects
reused ones as an ID collision. Pass `new` as the id the first time and the id
it prints thereafter.

Usage: repair.py <templateId|new> <path-to-generated.json>
"""
import json
import pathlib
import re
import sys
import uuid

sys.path.insert(0, str(pathlib.Path("~/.claude/skills/create-template-for-railway/scripts").expanduser()))
import rw  # noqa: E402

WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"  # Auromations
NAME = "Rakazo"
# Served from upstream's own repo, pinned to the release tag the image is built
# from, so a later upstream commit cannot change or 404 the listing icon.
ICON = "https://raw.githubusercontent.com/elie222/rakazo/v0.1.6/docs/readme-hero.png"

AUTH_HELP = (
    "Signs everyone's sessions. Generated for you. "
    "Changing it signs everybody out; it loses no data."
)
ENCRYPTION_HELP = (
    "Encrypts the provider keys and bot secrets people add inside the app. "
    "Generated for you. Changing it makes every stored key permanently "
    "unreadable, so leave it alone."
)
SCREEN_HELP = (
    "Guards the noVNC screen proxy used when bots have computers. Generated for "
    "you. Unused while SANDBOX_PROVIDER is none."
)
SANDBOX_HELP = (
    "Where bot computers run: none, e2b, daytona or box. Docker is not possible "
    "on Railway, so the default is none: bots chat and use tools but cannot "
    "open a desktop. Pick a provider and fill in its API key below to enable "
    "computers. Safe to change later with a redeploy."
)
OPENROUTER_HELP = (
    "Deployment-wide fallback model key. Optional: a model can also be "
    "connected in the UI after signup, where the app verifies the key before "
    "storing it. Every model call is billed to the key you provide."
)

VARIABLES = {
    # Railway's own Postgres config shape, lettertrace precedent. DATABASE_URL
    # lives here so the app can reference it by name rather than carry its own
    # copy of the password.
    "Postgres": {
        "PGDATA": {
            "isOptional": False,
            "description": "Where the database is initialized. A subdirectory of the mount, because a volume root is never empty and initdb refuses a non-empty directory.",
            "defaultValue": "/var/lib/postgresql/data/pgdata",
        },
        "PGHOST": {"isOptional": False, "defaultValue": "${{RAILWAY_PRIVATE_DOMAIN}}"},
        "PGPORT": {"isOptional": False, "defaultValue": "5432"},
        "PGUSER": {"isOptional": False, "defaultValue": "${{POSTGRES_USER}}"},
        "PGDATABASE": {"isOptional": False, "defaultValue": "${{POSTGRES_DB}}"},
        "PGPASSWORD": {"isOptional": False, "defaultValue": "${{POSTGRES_PASSWORD}}"},
        "POSTGRES_DB": {"isOptional": False, "defaultValue": "railway"},
        "POSTGRES_USER": {"isOptional": False, "defaultValue": "postgres"},
        "POSTGRES_PASSWORD": {
            "isOptional": False,
            "defaultValue": '${{ secret(32, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") }}',
        },
        "DATABASE_URL": {
            "isOptional": False,
            "defaultValue": "postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{PGDATABASE}}",
        },
        "SSL_CERT_DAYS": {"isOptional": False, "defaultValue": "820"},
        "RAILWAY_DEPLOYMENT_DRAINING_SECONDS": {"isOptional": False, "defaultValue": "60"},
    },
    "Rakazo": {
        "PORT": {
            "isOptional": False,
            "description": "Pinned to the port the public domain targets. Railway injects 8080 otherwise and the healthcheck drifts off the real listener.",
            "defaultValue": "5173",
        },
        "NODE_ENV": {"isOptional": False, "defaultValue": "production"},
        "DATABASE_URL": {
            "isOptional": False,
            "description": "Wired to the Postgres service in this template.",
            "defaultValue": "${{Postgres.DATABASE_URL}}",
        },
        "DATA_DIR": {"isOptional": False, "defaultValue": "/data"},
        "BETTER_AUTH_SECRET": {"isOptional": False, "description": AUTH_HELP, "defaultValue": "${{secret(32)}}"},
        "ENCRYPTION_KEY": {"isOptional": False, "description": ENCRYPTION_HELP, "defaultValue": '${{secret(64, "0123456789abcdef")}}'},
        "SCREEN_PROXY_SECRET": {"isOptional": False, "description": SCREEN_HELP, "defaultValue": "${{secret(32)}}"},
        "BETTER_AUTH_URL": {"isOptional": False, "defaultValue": "https://${{RAILWAY_PUBLIC_DOMAIN}}"},
        "WEB_ORIGIN": {"isOptional": False, "defaultValue": "https://${{RAILWAY_PUBLIC_DOMAIN}}"},
        "API_URL": {"isOptional": False, "defaultValue": "https://${{RAILWAY_PUBLIC_DOMAIN}}"},
        "RAKAZO_HOST": {
            "isOptional": False,
            "description": "The web server only answers requests for this hostname (vite allowedHosts). It is the public domain and never needs changing.",
            "defaultValue": "${{RAILWAY_PUBLIC_DOMAIN}}",
        },
        "SIGNUPS_ENABLED": {
            "isOptional": False,
            "description": "The first registered user becomes the deployment owner. Set to false after registering to close the instance.",
            "defaultValue": "true",
        },
        "SANDBOX_PROVIDER": {"isOptional": False, "description": SANDBOX_HELP, "defaultValue": "none"},
        "E2B_API_KEY": {"isOptional": True, "description": "Only when SANDBOX_PROVIDER is e2b.", "defaultValue": ""},
        "DAYTONA_API_KEY": {"isOptional": True, "description": "Only when SANDBOX_PROVIDER is daytona.", "defaultValue": ""},
        "BOX_API_KEY": {"isOptional": True, "description": "Only when SANDBOX_PROVIDER is box.", "defaultValue": ""},
        "OPENROUTER_API_KEY": {"isOptional": True, "description": OPENROUTER_HELP, "defaultValue": ""},
        "PI_DEFAULT_PROVIDER": {"isOptional": False, "defaultValue": "openrouter"},
    },
}

ICONS = {
    "Postgres": "https://devicons.railway.app/i/postgresql.svg",
    "Rakazo": ICON,
}


def main():
    template_id = sys.argv[1]
    config = json.loads(pathlib.Path(sys.argv[2]).read_text())
    if "templateGenerate" in config:
        config = config["templateGenerate"]["serializedConfig"]
    if template_id == "new":
        template_id = str(uuid.uuid4())
        remap = {sid: str(uuid.uuid4()) for sid in config["services"]}
        rebuilt = {"buckets": config.get("buckets", {}), "services": {}}
        for sid, svc in config["services"].items():
            svc = json.loads(json.dumps(svc))
            if svc.get("volumeMounts"):
                # Keyed by the owning service's id, so it has to move with it.
                svc["volumeMounts"] = {remap[k]: v for k, v in svc["volumeMounts"].items()}
            rebuilt["services"][remap[sid]] = svc
        config = rebuilt
        print("minting template", template_id)
    for service in config["services"].values():
        name = service["name"]
        service["variables"] = VARIABLES[name]
        service["icon"] = ICONS[name]
    saved = rw.gql(
        """mutation($id: String!, $input: TemplateUpsertConfigInput!) {
             templateUpsertConfig(id: $id, input: $input) { id code }
           }""",
        {"id": template_id,
         "input": {"name": NAME, "workspaceId": WORKSPACE,
                   "serializedConfig": config, "canvasConfig": {}}},
        internal=True,
    )["templateUpsertConfig"]
    print(f"saved  id {saved['id']}  code {saved['code']}")

    # Read it back. A write that returned success is not a write that landed,
    # and a reference keyed by UUID instead of by name resolves to an empty
    # string on every deploy while still reporting SUCCESS.
    back = rw.gql(
        "query($c: String!) { template(code: $c) { serializedConfig } }",
        {"c": saved["code"]},
    )["template"]["serializedConfig"]
    problems = []
    for service in back["services"].values():
        name = service["name"]
        want = VARIABLES[name]
        got = service.get("variables", {})
        for key, spec in want.items():
            if key not in got:
                problems.append(f"{name}.{key} missing")
                continue
            if got[key].get("defaultValue") != spec.get("defaultValue"):
                problems.append(
                    f"{name}.{key} default is {got[key].get('defaultValue')!r}, wanted {spec.get('defaultValue')!r}"
                )
        if service.get("icon") != ICONS[name]:
            problems.append(f"{name}.icon is {service.get('icon')!r}")
    app = next(s for s in back["services"].values() if s["name"] == "Rakazo")
    if app.get("deploy", {}).get("healthcheckPath") != "/api/auth/capabilities":
        problems.append(f"healthcheck is {app.get('deploy', {}).get('healthcheckPath')!r}")
    if app.get("deploy", {}).get("startCommand"):
        # A start command would replace the image entrypoint, which is the whole
        # boot sequence: volume chown, migrations, api + worker + web.
        problems.append(f"a start command crept in: {app['deploy']['startCommand']!r}")
    ports = [d.get("port") for d in app.get("networking", {}).get("serviceDomains", {}).values()]
    if ports != [5173]:
        problems.append(f"public address target port is {ports}, wanted [5173]")
    for svc_name in ("Postgres", "Rakazo"):
        svc = next(s for s in back["services"].values() if s["name"] == svc_name)
        if not svc.get("volumeMounts"):
            problems.append(f"{svc_name} lost its volume")
    # UUIDs inside a reference are the failure that looks exactly like a race.
    blob = json.dumps(back)
    for ref in re.findall(r"\$\{\{[^}]*\}\}", blob):
        if re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", ref):
            problems.append(f"reference keyed by UUID: {ref}")
    for line in problems:
        print("MISMATCH", line)
    print("clean" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
