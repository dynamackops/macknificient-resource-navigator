"""
Discovery & Vetting Agent — Macknificient World Resource Navigator.

Background agent, meant to run on a schedule (cron / EventBridge ->
AgentCore Runtime). Two passes:

- verify: re-checks existing resources.db entries for staleness (dead
  links, changed/discontinued info). Mechanically verifiable cases
  (link still resolves, content matches) are handled silently via
  mark_verified. Anything dead or ambiguous is escalated via
  flag_for_review rather than auto-deleted.
- discover: reads a curated list of Tampa/Hillsborough hub & directory
  pages per category, looks for resources not already in the database,
  and proposes them. Clear, non-duplicate finds are inserted directly
  (confidence='medium', pending human spot-check); anything that looks
  like a possible duplicate or has ambiguous eligibility is escalated.

Usage:
    python3 discovery_agent.py verify [--limit N]
    python3 discovery_agent.py discover [--category CATEGORY]
    python3 discovery_agent.py full [--limit N]   # verify then discover; cron-friendly
"""

import argparse

from strands import Agent
from strands.models import BedrockModel

from tools import query_resources, db_read, db_write, mark_verified, flag_for_review
from web_tools import fetch_url

# Curated hub/directory pages that list multiple resources per category —
# used for the discovery pass. Kept small and hand-picked (per the project
# plan) rather than open-ended web search, so the agent's search space
# stays trustworthy for a nonprofit-facing tool.
HUB_PAGES = {
    "mental_health": [
        "https://211tampabay.org/mental-health/",
        "https://hcfl.gov/residents/parks-and-leisure/mindful-mondays/organizations-offering-mental-health-resources",
    ],
    "neurodivergent": [
        "http://pepsaforum.cbcs.usf.edu/card-sg.php?county=Hillsborough",
        "https://liftfrc.org/community-partners/",
    ],
    "financial_assistance": [
        "https://211tampabay.org/",
        "https://bals.org/help/resources/tampa-bay-housing-emergency-list",
    ],
    "youth_activities": [
        "https://hcfl.gov/residents/parks-and-leisure/parks/register-for-a-park-program",
    ],
}

SYSTEM_PROMPT = """\
You are the Discovery & Vetting Agent for Macknificient World, a Tampa/\
Hillsborough County (Florida) nonprofit. You maintain resources.db, the \
database of vetted local resources (mental_health, neurodivergent, \
financial_assistance, youth_activities) that the Family Matching Agent \
searches on behalf of case workers and families.

You run unattended on a schedule. Your job is to keep the database \
current with as little human involvement as possible, but you must \
never silently make a judgment call that a human should make. Concretely:

MECHANICALLY VERIFIABLE — handle directly, no escalation:
- A resource's source_url still returns a working page (fetch_url ok=True,
  status_code 2xx) and the page content doesn't contradict what's stored
  (no "discontinued", "closed", "no longer offered", etc.) -> call
  mark_verified(resource_id).
- A newly discovered resource on a hub page is clearly not already in the
  database (distinct name/org, not a near-duplicate of an existing entry)
  and has enough information to fill required fields -> call db_write to
  insert it into 'resources' with action='insert', category matched to
  the hub page's category, confidence='medium' (it hasn't been human
  spot-checked yet), and source_url set to the specific page you found it
  on (not just the hub page, if a more specific link exists).

REQUIRES HUMAN JUDGMENT — call flag_for_review instead of deciding yourself:
- A resource's source_url is dead (4xx/5xx, timeout) or its content
  suggests the program is discontinued/changed — flag it with
  resource_id and a reason; do NOT delete or silently update eligibility/
  cost fields.
- A newly discovered candidate might be a duplicate of an existing entry
  (similar name, same org under a different program name, same contact
  info) — flag it with the reason and the candidate data; do NOT insert it.
- A candidate's eligibility, cost, or service area is ambiguous or you're
  not confident you extracted it correctly from the page — flag it with
  the candidate data rather than guessing.

Always check existing resources for a category (via db_read on
'resources' filtered by category, or query_resources) BEFORE proposing a
new insert, so you can catch duplicates.

Be economical with fetch_url calls — you're working within a tool-call
budget for this run. Report a short summary at the end: how many
resources you verified, how many you flagged and why, how many new
resources you inserted, and how many new candidates you flagged.
"""


def build_agent() -> Agent:
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region_name="us-east-1",
    )
    return Agent(
        model=model,
        tools=[query_resources, db_read, db_write, mark_verified, flag_for_review, fetch_url],
        system_prompt=SYSTEM_PROMPT,
    )


def run_verify(agent: Agent, limit: int) -> None:
    prompt = (
        f"Run a verification pass. Use db_read on 'resources' to list up "
        f"to {limit} resources (any category) and re-check each one's "
        f"source_url with fetch_url. For each: mark_verified if it's "
        f"still good, or flag_for_review if it's dead/ambiguous. Finish "
        f"with your summary."
    )
    agent(prompt)


def run_discover(agent: Agent, category: str | None) -> None:
    categories = [category] if category else list(HUB_PAGES)
    for cat in categories:
        pages = HUB_PAGES.get(cat, [])
        if not pages:
            continue
        prompt = (
            f"Run a discovery pass for category '{cat}'. First, use "
            f"db_read (table='resources', filters={{'category': '{cat}'}}) "
            f"to see what's already in the database for this category. "
            f"Then use fetch_url to read these hub/directory pages and "
            f"look for Tampa/Hillsborough resources in this category that "
            f"aren't already listed:\n"
            + "\n".join(f"- {p}" for p in pages)
            + "\nFor each candidate you find: insert it if it's clearly "
              "new and you have enough info, or flag_for_review if it "
              "might be a duplicate or the details are ambiguous. Finish "
              "with your summary."
        )
        agent(prompt)


def main():
    parser = argparse.ArgumentParser(description="Discovery & Vetting Agent")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_verify = sub.add_parser("verify", help="Re-check existing resources for staleness")
    p_verify.add_argument("--limit", type=int, default=8)

    p_discover = sub.add_parser("discover", help="Look for new candidate resources")
    p_discover.add_argument("--category", choices=list(HUB_PAGES), default=None)

    p_full = sub.add_parser("full", help="Verify then discover — intended for cron/EventBridge")
    p_full.add_argument("--limit", type=int, default=8)

    args = parser.parse_args()
    agent = build_agent()

    if args.mode == "verify":
        run_verify(agent, args.limit)
    elif args.mode == "discover":
        run_discover(agent, args.category)
    elif args.mode == "full":
        run_verify(agent, args.limit)
        run_discover(agent, None)


if __name__ == "__main__":
    main()
