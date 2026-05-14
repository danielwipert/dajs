"""Isolated OpenRouter smoke test — one bulk-scoring call against a fake job.

Run: python scripts/test_openrouter.py
Burns ~$0.001 in DeepSeek tokens. Confirms auth + structured-output parsing
against the BulkScoringOutput schema before integrating into Stage 4.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dajs.providers.openrouter import OpenRouterProvider
from dajs.schemas import BulkScoringOutput


SAMPLE_JOB_DESC = """
Forward Deployed Engineer at Tread

About Tread
Tread is an AI-native vertical SaaS platform transforming construction
materials logistics — a massive, essential industry that moves the aggregate,
asphalt, and concrete that build cities.

About the Role
As a Forward Deployed Engineer, you'll work directly with construction
materials companies to deploy our AI platform in their operations. You'll
spend roughly half your time embedded with customers — understanding their
workflows, configuring our system to fit their processes, and iterating
based on what you learn. The other half you'll spend in product engineering,
turning customer learnings into platform improvements.

What you'll do:
- Lead end-to-end customer deployments
- Build integrations between our platform and customer systems (ERPs,
  scale tickets, dispatch systems)
- Translate construction operations into product requirements
- Author technical documentation and customer playbooks

What we're looking for:
- 5+ years engineering experience, with significant time customer-facing
- Comfortable with Python, SQL, REST APIs
- Track record of shipping production systems in regulated environments
- Ability to translate between business stakeholders and engineering teams
"""


def main() -> None:
    load_dotenv()
    cfg = yaml.safe_load(Path("config/scoring.yaml").read_text(encoding="utf-8"))
    resume = Path("config/resume.txt").read_text(encoding="utf-8")

    system = (
        "You are a hiring-fit evaluator scoring jobs against Daniel Wipert's resume. "
        "Score four dimensions on a 0-100 integer scale: role_fit_score, "
        "experience_match_score, mission_fit_score, seniority_match_score. "
        "Provide a one-sentence justification per dimension in the justifications "
        "object (keys: role_fit, experience_match, mission_fit, seniority_match). "
        "Be calibrated — 70 means clearly qualified; 85+ means exceptional fit."
    )
    user = (
        f"DANIEL'S RESUME:\n{resume}\n\n"
        f"JOB POSTING:\n{SAMPLE_JOB_DESC}"
    )

    provider = OpenRouterProvider()
    print(f"model: {cfg['bulk_model']}")
    result = provider.complete(system, user, cfg["bulk_model"], BulkScoringOutput)

    print()
    print(f"role_fit_score:        {result.role_fit_score}")
    print(f"experience_match_score: {result.experience_match_score}")
    print(f"mission_fit_score:      {result.mission_fit_score}")
    print(f"seniority_match_score:  {result.seniority_match_score}")
    composite = (
        result.role_fit_score
        + result.experience_match_score
        + result.mission_fit_score
        + result.seniority_match_score
    ) / 4
    print(f"composite (avg):        {composite:.1f}")
    print()
    for k, v in result.justifications.items():
        print(f"  {k}: {v}")
    print()
    u = provider.usage
    print(
        f"Usage: {u.calls} call, "
        f"{u.prompt_tokens} prompt + {u.completion_tokens} completion tokens, "
        f"cost ${u.cost_usd:.5f}"
    )


if __name__ == "__main__":
    main()
