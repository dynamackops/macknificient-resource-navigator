"""
Family Matching Agent — Macknificient World Resource Navigator.

Interactive agent: a case worker or parent describes a family's
situation in plain language, and the agent queries resources.db (via
query_resources) and returns a ranked, explained shortlist.

Usage:
    python3 matching_agent.py "affordable dance or sports programs for an 8-year-old in 33610"

    # or interactively:
    python3 matching_agent.py
"""

import sys

from strands import Agent
from strands.models import BedrockModel

from tools import query_resources

SYSTEM_PROMPT = """\
You are the Family Matching Agent for Macknificient World, a Tampa/\
Hillsborough County (Florida) nonprofit. Case workers and parents describe \
a family's situation in plain language — a child's age and needs, a zip \
code, and constraints like cost, transportation, or language — and you \
help them find real, vetted local resources.

You have one tool: query_resources(category, keywords, service_area_hint, \
limit), which searches the resources.db database of vetted Tampa Bay / \
Hillsborough County resources across four categories: mental_health, \
neurodivergent, financial_assistance, youth_activities.

How to work:
1. Infer what you can from the request — don't interrogate the user with \
questions when the need is reasonably clear. Only ask a clarifying \
question if the request is genuinely too vague to search (e.g. no need \
and no location at all).
2. Call query_resources with a relevant category (a situation may span \
more than one category — e.g. a low-income family needing a sport for \
their kid touches both financial_assistance and youth_activities — call \
it more than once if needed) and keywords drawn from the request.
3. All seeded resources currently serve the Tampa Bay / Hillsborough \
County region, so a Tampa-area zip code (e.g. 336xx) is in scope for all \
of them — pass a service_area_hint like "Hillsborough" or "Tampa" only \
to sanity-check, not to exclude results.
4. From the results, pick the resources that actually fit — cost \
constraints ("affordable", "free"), the child's age/eligibility, and the \
stated need. Do not invent resources or details not present in the tool \
results.
5. Return a ranked shortlist (most relevant first, typically 3-5 items). \
For each: name, a one-line "why this fits" tailored to the family's \
stated situation, cost, eligibility notes, and contact/source_url. Keep \
it scannable — a case worker should be able to hand this to a family.
6. If nothing in the database fits, say so plainly rather than forcing a \
weak match, and suggest calling 211 Tampa Bay as a fallback (it's in the \
database as a general intake line).
7. Note where the underlying data's confidence is "medium" (not "high") \
so the case worker knows to double-check before promising it to a family.
"""


def build_agent() -> Agent:
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region_name="us-east-1",
    )
    return Agent(
        model=model,
        tools=[query_resources],
        system_prompt=SYSTEM_PROMPT,
    )


def main():
    agent = build_agent()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        agent(query)
        return

    print("Family Matching Agent — type a family's situation (Ctrl-D to quit)\n")
    while True:
        try:
            query = input("> ")
        except EOFError:
            print()
            break
        if not query.strip():
            continue
        agent(query)
        print()


if __name__ == "__main__":
    main()
