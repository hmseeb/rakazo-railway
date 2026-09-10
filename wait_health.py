#!/usr/bin/env python3
"""Poll latest deployment of a service until terminal; print status + tail of logs."""
import pathlib, sys, time
sys.path.insert(0, str(pathlib.Path("~/.claude/skills/create-template-for-railway/scripts").expanduser()))
import rw  # noqa: E402
svc, env = sys.argv[1], sys.argv[2]
for _ in range(60):
    d = rw.gql("""query($s: String!, $e: String!) { deployments(first: 1, input: {serviceId: $s, environmentId: $e}) { edges { node { id status } } } }""",
               {"s": svc, "e": env})["deployments"]["edges"][0]["node"]
    print(d["status"], flush=True)
    if d["status"] in ("SUCCESS", "FAILED", "CRASHED", "REMOVED"):
        break
    time.sleep(10)
logs = rw.gql("""query($id: String!) { deploymentLogs(deploymentId: $id, limit: 60) { message } }""", {"id": d["id"]})["deploymentLogs"]
print("\n".join(l["message"] for l in logs))
