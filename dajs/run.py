"""DAJS orchestrator entry point.

Phase 1: wires up stub providers and prints the init message.
Subsequent phases progressively replace stubs with real providers and add stages.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

from dajs.providers.stub_llm import StubLLMProvider
from dajs.providers.stub_search import StubSearchProvider


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_configs() -> dict:
    """Load every YAML config in config/ into a single dict keyed by filename stem."""
    configs: dict[str, dict] = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        configs[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return configs


def main() -> None:
    load_dotenv()
    configs = load_configs()

    # Provider wiring. Swapped to real providers in Phase 2 / Phase 4.
    search_provider = StubSearchProvider()
    llm_provider = StubLLMProvider()

    print("DAJS pipeline initialized")
    print(f"  configs loaded: {sorted(configs.keys())}")
    print(f"  search provider: {type(search_provider).__name__}")
    print(f"  llm provider: {type(llm_provider).__name__}")


if __name__ == "__main__":
    main()
