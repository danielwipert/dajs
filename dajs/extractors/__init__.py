"""Extractor dispatcher — routes a fetched ATS page to its platform-specific
extractor module.

The signature is `extract_job(html, url, ats) -> ExtractedJob`. Stage 3
(enrich) is responsible for fetching the HTML and constructing the EnrichedJob
from the returned dict plus the upstream FilteredJob fields.
"""

from __future__ import annotations

import logging

from dajs.extractors import (
    ashby,
    bamboohr,
    dover,
    greenhouse,
    lever,
    recruitee,
    smartrecruiters,
)
from dajs.extractors.base import ExtractedJob
from dajs.schemas import ATSPlatform

log = logging.getLogger(__name__)

_EXTRACTORS = {
    ATSPlatform.GREENHOUSE: greenhouse.extract,
    ATSPlatform.LEVER: lever.extract,
    ATSPlatform.ASHBY: ashby.extract,
    ATSPlatform.DOVER: dover.extract,
    ATSPlatform.BAMBOOHR: bamboohr.extract,
    ATSPlatform.RECRUITEE: recruitee.extract,
    ATSPlatform.SMARTRECRUITERS: smartrecruiters.extract,
}


def extract_job(html: str, url: str, ats: ATSPlatform) -> ExtractedJob:
    fn = _EXTRACTORS.get(ats)
    if fn is None:
        raise KeyError(f"No extractor registered for ATS platform {ats}")
    return fn(html, url)
