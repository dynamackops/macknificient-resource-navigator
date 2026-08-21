# Macknificient World Resource Navigator

Built for the [AWS Agents for Humans Hackathon](https://aws.amazon.com/) — Good Neighbor Agents track.

A two-agent system, built on the [Strands Agents SDK](https://strandsagents.com/), that finds and matches
mental health, neurodivergent-support, financial-assistance, and affordable-activity resources for families
in the Tampa Bay area — built for [Macknificient World Inc.](https://mackworldinc.org)'s case workers and the
families they serve.

## The problem

Parents and caregivers — especially those raising neurodivergent kids, managing a child's mental health, or
stretched thin financially — lose hours piecing together information scattered across dozens of disconnected
sources. Macknificient World's case workers face the same problem at scale, redoing the same manual research
for every family they help.

## What it does

- **Discovery & Vetting Agent** (background, scheduled) — searches and verifies local resource listings,
  keeps the database current, and only escalates ambiguous or duplicate cases to a human reviewer.
- **Family Matching Agent** (interactive) — takes a plain-language description of a family's situation and
  returns a ranked, explained shortlist of matching resources.

See `docs/PLAN.md` for the full project plan, architecture, and scope.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

aws configure   # region: us-east-1
# then enable Claude model access in the Bedrock console: Bedrock → Model access

python3 seed_db.py   # loads seed_resources.json into resources.db
```

## Running the Family Matching Agent

```bash
python3 matching_agent.py "affordable dance or sports programs for an 8-year-old in 33610"

# or interactively:
python3 matching_agent.py
```

It queries `resources.db` via the `query_resources` tool (`tools.py`) and returns a ranked,
explained shortlist using Claude on Amazon Bedrock.

## Tech stack

- [Strands Agents SDK](https://strandsagents.com/) (Python)
- Amazon Bedrock (Claude) as the model provider
- SQLite for local development (DynamoDB if deployed to AgentCore)

## License

MIT — see [LICENSE](./LICENSE).
