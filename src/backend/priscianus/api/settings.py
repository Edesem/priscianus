"""Settings the API reads from the environment (ADR-005, Decision 7).

`ANTHROPIC_API_KEY` is not here: the Anthropic SDK reads it by itself when the client is built.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from priscianus.llm.client import DEFAULT_DB as DEFAULT_LLM_DB
from priscianus.morphology.build_index import DEFAULT_DB as DEFAULT_MORPHOLOGY_DB

DEFAULT_LIMITS_DB = Path("limits.db")

# Where `make dev` serves the front end.
DEFAULT_ORIGINS = ("http://localhost:5173",)


@dataclass(frozen=True)
class Settings:
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
    morphology_db: Path = DEFAULT_MORPHOLOGY_DB
    llm_db: Path = DEFAULT_LLM_DB
    limits_db: Path = DEFAULT_LIMITS_DB
    daily_request_limit: int = 20
    ip_daily_limit: int = 20
    daily_spend_cap_usd: float = 0.50
    ip_hash_salt: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        """`ALLOWED_ORIGINS` is a comma-separated list. Anything not set keeps its default."""
        origins = os.environ.get("ALLOWED_ORIGINS")
        return cls(
            allowed_origins=(
                tuple(o.strip() for o in origins.split(",") if o.strip())
                if origins is not None
                else DEFAULT_ORIGINS
            ),
            morphology_db=Path(os.environ.get("MORPHOLOGY_DB", DEFAULT_MORPHOLOGY_DB)),
            llm_db=Path(os.environ.get("LLM_DB", DEFAULT_LLM_DB)),
            limits_db=Path(os.environ.get("LIMITS_DB", DEFAULT_LIMITS_DB)),
            daily_request_limit=int(os.environ.get("DAILY_REQUEST_LIMIT", 20)),
            ip_daily_limit=int(os.environ.get("IP_DAILY_LIMIT", 20)),
            daily_spend_cap_usd=float(os.environ.get("DAILY_SPEND_CAP_USD", 0.50)),
            ip_hash_salt=os.environ.get("IP_HASH_SALT", ""),
        )
