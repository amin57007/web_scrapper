"""Runtime settings loaded from flags and environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_BASE_URL = "https://app.ultralibrarian.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Live export checkbox values from app.ultralibrarian.com (KiCAD v6+ and STEP).
KICAD_V6_EXPORT_ID = 42
KICAD_V5_EXPORT_ID = 24
STEP_EXPORT_ID = 37

DEFAULT_EXPORT_IDS = (KICAD_V6_EXPORT_ID, STEP_EXPORT_ID)


class Settings(BaseModel):
    """Client configuration. Environment wins over constructor defaults."""

    base_url: str = Field(default=DEFAULT_BASE_URL)
    user_agent: str = Field(default=DEFAULT_USER_AGENT)
    email: str | None = None
    password: str | None = None
    cookies_path: Path | None = None
    timeout_s: float = 30.0
    poll_interval_s: float = 2.0
    poll_timeout_s: float = 180.0
    output_dir: Path = Field(default_factory=lambda: Path("libraries"))

    @classmethod
    def from_env(cls, **overrides: object) -> Settings:
        data: dict[str, object] = {
            "base_url": os.environ.get("UL_BASE_URL", DEFAULT_BASE_URL),
            "user_agent": os.environ.get("UL_USER_AGENT", DEFAULT_USER_AGENT),
            "email": os.environ.get("UL_EMAIL") or None,
            "password": os.environ.get("UL_PASSWORD") or None,
            "timeout_s": float(os.environ.get("UL_TIMEOUT", "30")),
        }
        cookies = os.environ.get("UL_COOKIES")
        if cookies:
            data["cookies_path"] = Path(cookies)
        output = os.environ.get("UL_OUTPUT")
        if output:
            data["output_dir"] = Path(output)
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls.model_validate(data)
