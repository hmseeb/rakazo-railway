#!/usr/bin/env python3
"""Publishes the template to the marketplace. Runs exactly once: the slug is
minted from the name here and never follows a later rename, and republishing an
already-published template mints an ugly suffixed slug."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("~/.claude/skills/create-template-for-railway/scripts").expanduser()))
import rw  # noqa: E402

TEMPLATE_ID = "f4af9e50-05a3-4925-a48d-fdacd2595720"
WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"  # Auromations
# 75 characters is the hard limit and Railway truncates silently past it. This
# is the field marketplace search actually reads, so the keywords live here
# rather than in the name, where they would only cost a worse permanent URL.
DESCRIPTION = "Persistent AI teammates with memory and routines. BYO model key"
README = (pathlib.Path(__file__).parent / "TEMPLATE_OVERVIEW.md").read_text()
assert len(DESCRIPTION) <= 75, len(DESCRIPTION)

published = rw.gql(
    """mutation($id: String!, $input: TemplatePublishInput!) {
         templatePublish(id: $id, input: $input) { id code isApproved }
       }""",
    {"id": TEMPLATE_ID,
     "input": {"category": "AI/ML", "description": DESCRIPTION, "readme": README, "workspaceId": WORKSPACE}},
)["templatePublish"]
print(published)
print(f"https://railway.com/deploy/{published['code']}")
