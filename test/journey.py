#!/usr/bin/env python3
"""Real user journey against a deployed Rakazo, over the same HTTP the web app uses.

1. OWNER_EMAIL signs in with OWNER_PASSWORD (bootstrap ran on first boot).
2. A stranger's sign-up is refused (signups closed).
3. The owner connects a model with their own key (the app verifies it with the provider).
4. The owner messages the starter bot and waits for a model-written reply.

Usage: ANTHROPIC_API_KEY=... journey.py <base-url> <owner-email> <owner-password-file> [model-id]
The key is read from the environment and never printed. Steps 3-4 are skipped
when ANTHROPIC_API_KEY is unset.
"""
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

base, email, pw_file = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
model_hint = sys.argv[4] if len(sys.argv) > 4 else "haiku"
password = open(pw_file).read().strip()
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def post(path, body, ok=(200,)):
    req = urllib.request.Request(
        base + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Origin": base},
    )
    try:
        with opener.open(req, timeout=60) as r:
            code, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read()
    data = json.loads(raw or b"null")
    if code not in ok:
        raise SystemExit(f"FAIL {path} -> {code} {json.dumps(data)[:400]}")
    return code, data


def rpc(path, inp=None):
    return post("/rpc/" + path, {} if inp is None else {"json": inp})[1]["json"]


code, data = post("/api/auth/sign-in/email", {"email": email, "password": password})
print("1 owner sign-in", code, {k: data["user"][k] for k in ("email", "emailVerified")})

code, data = post("/api/auth/sign-up/email",
                  {"email": "stranger@example.com", "password": "stranger-pw-0123456789", "name": "x"},
                  ok=(400, 403))
print("2 stranger sign-up", code, data.get("code"))

bots = rpc("bots/list")
print("  bots:", [b.get("name") for b in bots])

key = os.environ.get("ANTHROPIC_API_KEY")
if not key:
    print("3-4 skipped: no ANTHROPIC_API_KEY")
    sys.exit(0)

catalog = rpc("models/list")
anthropic = [m for m in catalog if m.get("provider") == "anthropic"]
pick = next((m for m in anthropic if model_hint in m.get("id", "")), None)
if not pick:
    raise SystemExit(f"FAIL no anthropic model matching {model_hint!r}: {[m.get('id') for m in anthropic][:20]}")
cred = rpc("models/connect", {"provider": "anthropic", "apiKey": key, "modelId": pick["id"], "credentialId": None})
print("3 model connected", pick["id"], {k: cred.get(k) for k in ("provider", "label")})

if bots:
    bot = bots[0]
else:  # bootstrap-owner accounts skip the onboarding that seeds the starter bot
    bot = rpc("bots/create", {"name": "Journey", "instructions": "Answer briefly."})
    print("  created bot", bot["name"], bot["id"])
sent = rpc("threads/send", {"botId": bot["id"], "text": "Reply with exactly the word: pineapple"})
print("4 sent to", bot.get("name"), "run", sent["runId"])
reply = None
for _ in range(36):
    time.sleep(5)
    page = rpc("threads/messages", {"botId": bot["id"]})
    for m in page.get("messages", []):
        if m.get("role") in ("assistant", "bot") or m.get("authorKind") == "bot" or m.get("botId") == bot["id"]:
            text = json.dumps(m.get("blocks", m))
            # The prompt itself also says pineapple; only a reply without it counts.
            if "pineapple" in text.lower() and "reply with" not in text.lower():
                reply = text
    if reply:
        break
if not reply:
    raise SystemExit(f"FAIL no bot reply containing 'pineapple'; last page: {json.dumps(page)[:1500]}")
print("4 bot reply:", reply[:300])
print("PASS journey")
