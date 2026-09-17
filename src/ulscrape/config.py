"""Runtime settings loaded from flags and environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

_LLM_KEY_VARS = (
    "UL_LLM_API_KEY",
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


def load_dotenv(path: Path | None = None) -> Path | None:
    """Load KEY=VALUE pairs from a .env file without overriding the process env.

    Looks at ``path``, then ``./.env``, then the repository root next to this package.
    Returns the file that was read, or None.
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    else:
        candidates.append(Path.cwd() / ".env")
        candidates.append(Path(__file__).resolve().parents[2] / ".env")
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        for raw in resolved.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
        return resolved
    return None


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
    storage_state_path: Path | None = None
    captcha_api_key: str | None = None
    captcha_provider: str = "2captcha"
    llm_api_key: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    use_browser: bool = True
    headed: bool = False
    timeout_s: float = 30.0
    poll_interval_s: float = 2.0
    poll_timeout_s: float = 180.0
    output_dir: Path = Field(default_factory=lambda: Path("libraries"))

    @classmethod
    def from_env(cls, **overrides: object) -> Settings:
        load_dotenv()
        data: dict[str, object] = {
            "base_url": os.environ.get("UL_BASE_URL", DEFAULT_BASE_URL),
            "user_agent": os.environ.get("UL_USER_AGENT", DEFAULT_USER_AGENT),
            "email": os.environ.get("UL_EMAIL") or None,
            "password": os.environ.get("UL_PASSWORD") or None,
            "timeout_s": float(os.environ.get("UL_TIMEOUT", "30")),
            "captcha_api_key": (
                os.environ.get("TWOCAPTCHA_API_KEY")
                or os.environ.get("CAPTCHA_API_KEY")
                or os.environ.get("CAPSOLVER_API_KEY")
                or None
            ),
            "captcha_provider": os.environ.get("UL_CAPTCHA_PROVIDER")
            or (
                "capsolver"
                if os.environ.get("CAPSOLVER_API_KEY")
                and not os.environ.get("TWOCAPTCHA_API_KEY")
                else "2captcha"
            ),
            "use_browser": os.environ.get("UL_USE_BROWSER", "1") not in {"0", "false", "False"},
            "headed": os.environ.get("UL_HEADED", "0") in {"1", "true", "True"},
            "llm_api_key": next(
                (os.environ[name] for name in _LLM_KEY_VARS if os.environ.get(name)),
                None,
            ),
            "llm_provider": os.environ.get("UL_LLM_PROVIDER") or None,
            "llm_model": os.environ.get("UL_LLM_MODEL") or None,
            "llm_base_url": os.environ.get("OPENAI_BASE_URL") or os.environ.get("UL_LLM_BASE_URL") or None,
        }
        cookies = os.environ.get("UL_COOKIES")
        if cookies:
            data["cookies_path"] = Path(cookies)
        storage = os.environ.get("UL_STORAGE")
        if storage:
            data["storage_state_path"] = Path(storage)
        output = os.environ.get("UL_OUTPUT")
        if output:
            data["output_dir"] = Path(output)
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls.model_validate(data)
