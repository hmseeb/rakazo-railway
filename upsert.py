#!/usr/bin/env python3
"""Moves the published template onto the image tag in template.json.

Starts from the LIVE serializedConfig (repair.py predates the r2 variables and
would wipe OWNER_EMAIL/OWNER_PASSWORD), changes only the Rakazo image and the
SANDBOX_PROVIDER help text, then either writes the result to a file (for a
stranger deploy before anything is live) or upserts it and reads it back.

Usage: upsert.py --print <out.json>     # build only, nothing written to Railway
       upsert.py --apply                # templateUpsertConfig + readback
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("~/.claude/skills/create-template-for-railway/scripts").expanduser()))
import rw  # noqa: E402

HERE = pathlib.Path(__file__).parent
TEMPLATE_ID = "f4af9e50-05a3-4925-a48d-fdacd2595720"
CODE = "rakazo-single-container"
WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"  # Auromations
IMAGE = json.loads((HERE / "template.json").read_text())["image"]["ref"]
SANDBOX_HELP = (
    "Where bot computers run: none, e2b or daytona. Docker is not possible "
    "on Railway, so the default is none: bots chat and use tools but cannot "
    "open a desktop. Pick a provider and fill in its API key below to enable "
    "computers. Safe to change later with a redeploy."
)


def build():
    t = rw.gql("query($c: String!) { template(code: $c) { name serializedConfig } }", {"c": CODE})["template"]
    config = t["serializedConfig"]
    app = next(s for s in config["services"].values() if s["name"] == "Rakazo")
    app["source"]["image"] = IMAGE
    app["variables"]["SANDBOX_PROVIDER"]["description"] = SANDBOX_HELP
    return t["name"], config


def main():
    name, config = build()
    if sys.argv[1] == "--print":
        pathlib.Path(sys.argv[2]).write_text(json.dumps(config, indent=2))
        print("wrote", sys.argv[2], "image", IMAGE)
        return
    assert sys.argv[1] == "--apply"
    rw.gql(
        """mutation($id: String!, $input: TemplateUpsertConfigInput!) {
             templateUpsertConfig(id: $id, input: $input) { id code }
           }""",
        {"id": TEMPLATE_ID, "input": {"name": name, "workspaceId": WORKSPACE,
                                      "serializedConfig": config, "canvasConfig": {}}},
        internal=True,
    )
    back = rw.gql("query($c: String!) { template(code: $c) { id code status serializedConfig } }", {"c": CODE})["template"]
    got = next(s for s in back["serializedConfig"]["services"].values() if s["name"] == "Rakazo")
    ok = back["id"] == TEMPLATE_ID and got["source"]["image"] == IMAGE and back["serializedConfig"] == config
    print(back["code"], back["status"], got["source"]["image"], "readback identical" if ok else "READBACK MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
