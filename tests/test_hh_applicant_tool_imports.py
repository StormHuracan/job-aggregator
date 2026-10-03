from pathlib import Path


def test_hh_applicant_tool_imported_only_inside_hh_integration_layer() -> None:
    project_root = Path("src/job_aggregator")
    allowed_dir = project_root / "integrations" / "hh"
    violations: list[str] = []

    for path in project_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")

        if "hh_applicant_tool" not in text:
            continue

        if allowed_dir not in path.parents:
            violations.append(str(path))

    assert violations == []
