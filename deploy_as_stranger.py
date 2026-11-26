#!/usr/bin/env python3
"""Clicks the deploy button the way a stranger would: no projectId, so Railway
makes a fresh project. The optional variables keep their defaults; the one
required prompt, OWNER_EMAIL, is filled in like the deploy form does.

Usage: deploy_as_stranger.py <owner-email> [config.json]
  config.json: a serializedConfig to deploy (upsert.py --print), so a new image
  can be tested before the live template changes. Default: the live template.
Test deploys go to My Projects (workspace rule since 2026-11-26)."""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path("~/.claude/skills/create-template-for-railway/scripts").expanduser()))
import rw  # noqa: E402

TEMPLATE_ID = "f4af9e50-05a3-4925-a48d-fdacd2595720"
WORKSPACE_ID = "d10da65a-297f-4ba4-8cef-2fa9bb45fdef"  # My Projects (test deploys)

owner_email = sys.argv[1]
if len(sys.argv) > 2:
    config = json.loads(pathlib.Path(sys.argv[2]).read_text())
else:
    config = rw.gql(
        "query($id: String!) { template(id: $id) { serializedConfig } }",
        {"id": TEMPLATE_ID},
    )["template"]["serializedConfig"]
app = next(s for s in config["services"].values() if s["name"] == "Rakazo")
app["variables"]["OWNER_EMAIL"]["defaultValue"] = owner_email
print("deploying image", app["source"]["image"])

result = rw.gql(
    """mutation($input: TemplateDeployV2Input!) {
         templateDeployV2(input: $input) { projectId workflowId }
       }""",
    {"input": {"templateId": TEMPLATE_ID, "workspaceId": WORKSPACE_ID, "serializedConfig": config}},
)["templateDeployV2"]
project_id = result["projectId"]
print("fresh project:", project_id, flush=True)

states = []
for _ in range(60):
    time.sleep(10)
    project = rw.gql(
        """query($id: String!) {
             project(id: $id) {
               name
               environments { edges { node { id name } } }
               services { edges { node {
                 id name
                 serviceInstances { edges { node {
                   latestDeployment { id status }
                   domains { serviceDomains { domain } }
                 } } }
               } } }
             }
           }""",
        {"id": project_id},
    )["project"]
    states = []
    for edge in project["services"]["edges"]:
        node = edge["node"]
        for inst in node["serviceInstances"]["edges"]:
            dep = inst["node"]["latestDeployment"]
            states.append(
                (node["name"], dep["status"] if dep else "none",
                 [d["domain"] for d in inst["node"]["domains"]["serviceDomains"]])
            )
    print("  ", states, flush=True)
    if states and all(s[1] in ("SUCCESS", "FAILED", "CRASHED") for s in states):
        break

print(json.dumps({
    "projectId": project_id,
    "projectName": project["name"],
    "environmentId": project["environments"]["edges"][0]["node"]["id"],
    "services": {e["node"]["name"]: e["node"]["id"] for e in project["services"]["edges"]},
    "states": states,
}, indent=2))
