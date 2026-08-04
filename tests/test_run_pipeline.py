"""run_pipeline.py itself: guards on the CLI surface that unit tests on the
sami package can't see, since the script is never imported as a module.
"""
from pathlib import Path


def test_run_pipeline_has_no_skip_nlp_argument():
    """Clustering IS the categorisation now, so a non-NLP run cannot produce
    a valid export — the flag must not exist, not even as dead text."""
    src = Path(__file__).resolve().parents[1] / "run_pipeline.py"
    text = src.read_text(encoding="utf-8")
    assert "--skip-nlp" not in text
    assert "skip_nlp" not in text
