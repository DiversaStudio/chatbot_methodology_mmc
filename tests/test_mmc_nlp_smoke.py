# tests/test_mmc_nlp_smoke.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_nlp
import numpy as np


def test_zeroshot_small(tmp_path):
    msgs = ["Cómo solicitar el salvoconducto", "Para empleo formal"]
    out = mmc_nlp.zeroshot_tint(msgs, cache=str(tmp_path / "z.parquet"))
    assert list(out["message"]) == msgs
    assert out.loc[0, "mmc_category"] == "legal documentation"
    assert out.loc[1, "mmc_category"] == "employment"
    assert (out["conf"] > 0.5).all()


def test_embed_cache_invalidates_on_content_change(tmp_path):
    """Verify that embed_messages rebuilds when message content changes, not just count."""
    cache_path = str(tmp_path / "e.npy")

    # First call with two messages
    msgs_a = ["hola mundo", "otro mensaje"]
    a = mmc_nlp.embed_messages(msgs_a, cache=cache_path)

    # Second call with different same-length messages
    msgs_b = ["mensaje distinto", "y otro mas"]
    b = mmc_nlp.embed_messages(msgs_b, cache=cache_path)

    # Verify shapes match
    assert a.shape[0] == 2
    assert b.shape[0] == 2
    assert a.shape == b.shape

    # Verify content changed (not same as cached)
    assert not np.array_equal(a, b), "Cache should be invalidated on content change"
