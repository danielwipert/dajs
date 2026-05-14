"""Stub search provider — returns canned RawJobs for offline pipeline development.

The fixture is intentionally mixed so downstream filter stages have real signal:
  - 3 jobs on approved ATS platforms in approved locations (should survive)
  - 1 job on an approved ATS but in a non-approved city (should be filter-dropped)
  - 1 job on a banned ATS (Workday) (should be filter-dropped)
"""

from __future__ import annotations

from dajs.schemas import RawJob


_FIXTURE = [
    {
        "title": "Forward Deployed Engineer",
        "company": "Acme AI",
        "location": "Chicago, IL",
        "apply_url": "https://boards.greenhouse.io/acmeai/jobs/4001",
        "posted_date": "2 days ago",
        "snippet": "Work directly with customers to deploy our AI platform...",
    },
    {
        "title": "Solutions Engineer, Applied AI",
        "company": "Brightside Labs",
        "location": "Remote - US",
        "apply_url": "https://jobs.lever.co/brightside/abc-123",
        "posted_date": "1 day ago",
        "snippet": "Partner with enterprise customers on AI deployments...",
    },
    {
        "title": "AI Implementation Engineer",
        "company": "Cobalt Systems",
        "location": "Austin, TX",
        "apply_url": "https://jobs.ashbyhq.com/cobalt/eng-implementation",
        "posted_date": "today",
        "snippet": "Build production deployments of our enterprise AI suite...",
    },
    {
        "title": "Customer Engineer",
        "company": "Helio Corp",
        "location": "San Francisco, CA",
        "apply_url": "https://boards.greenhouse.io/helio/jobs/9001",
        "posted_date": "3 days ago",
        "snippet": "Drive customer success in SF Bay Area...",
    },
    {
        "title": "Deployment Engineer",
        "company": "Megacorp",
        "location": "Chicago, IL",
        "apply_url": "https://megacorp.wd1.myworkdayjobs.com/en-US/careers/jobs/deploy-eng",
        "posted_date": "1 day ago",
        "snippet": "Lead enterprise deployments...",
    },
]


class StubSearchProvider:
    """Returns the same canned fixture every call. Ignores query and params."""

    def search(self, query: str, params: dict) -> list[RawJob]:
        return [RawJob(**job) for job in _FIXTURE]
