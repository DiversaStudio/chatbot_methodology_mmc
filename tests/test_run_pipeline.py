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


def test_nlp_meta_carries_the_subcluster_keys():
    """The five meta_run keys schema v6 promises. Guards against a wiring change
    that drops one silently — meta_run is the run's identity card and a missing
    key is invisible until someone asks the dashboard a question it can't answer.
    """
    import inspect
    import run_pipeline

    src = inspect.getsource(run_pipeline._nlp_tables)
    for key in ("n_subclusters", "n_parents_split", "n_provisional_subnames",
                "subcluster_min_users", "subcluster_stability_ari"):
        assert f'"{key}"' in src, f"{key} missing from nlp_meta"
