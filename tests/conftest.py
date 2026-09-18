from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.helpers import write_ul_zip

# Keep a developer .env (OpenAI key, UL login) out of unit tests.
os.environ["UL_SKIP_DOTENV"] = "1"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def details_html() -> str:
    return (FIXTURES / "details_opa2374.html").read_text(encoding="utf-8")


@pytest.fixture
def adrf_details_html() -> str:
    return (FIXTURES / "details_adrf5051.html").read_text(encoding="utf-8")


@pytest.fixture
def ul_zip(tmp_path: Path) -> Path:
    return write_ul_zip(tmp_path / "ul_OPA2374AIDR.zip")
