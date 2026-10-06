import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from job_aggregator.integrations.hh import HHVacancySearchParams


def test_search_params_defaults() -> None:
    params = HHVacancySearchParams(text="python")
    assert params.text == "python"
    assert params.area is None
    assert params.page == 0
    assert params.per_page == 20


def test_search_params_all_fields() -> None:
    params = HHVacancySearchParams(text="python", area="1", page=3, per_page=50)
    assert params.area == "1"
    assert params.page == 3
    assert params.per_page == 50


def test_search_params_strips_text() -> None:
    params = HHVacancySearchParams(text="  python developer  ")
    assert params.text == "python developer"


@pytest.mark.parametrize("per_page", [1, 100])
def test_search_params_per_page_bounds_allowed(per_page: int) -> None:
    params = HHVacancySearchParams(text="python", per_page=per_page)
    assert params.per_page == per_page


@pytest.mark.parametrize("text", ["", " ", "   \t\n"])
def test_search_params_rejects_blank_text(text: str) -> None:
    with pytest.raises(ValidationError):
        HHVacancySearchParams(text=text)


def test_search_params_requires_text() -> None:
    with pytest.raises(ValidationError):
        HHVacancySearchParams()  # type: ignore[call-arg]


def test_search_params_rejects_negative_page() -> None:
    with pytest.raises(ValidationError):
        HHVacancySearchParams(text="python", page=-1)


@pytest.mark.parametrize("per_page", [0, -1, 101])
def test_search_params_rejects_per_page_out_of_range(per_page: int) -> None:
    with pytest.raises(ValidationError):
        HHVacancySearchParams(text="python", per_page=per_page)


def test_hh_package_does_not_import_heavy_dependencies() -> None:
    code = (
        "import sys\n"
        "import job_aggregator.integrations.hh\n"
        "forbidden = ('fastapi', 'sqlalchemy', 'hh_applicant_tool')\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    src_dir = Path(__file__).resolve().parents[1] / "src"
    env = {**os.environ, "PYTHONPATH": str(src_dir)}
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
