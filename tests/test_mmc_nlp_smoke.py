# tests/test_mmc_nlp_smoke.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_nlp


def test_zeroshot_small(tmp_path):
    msgs = ["Cómo solicitar el salvoconducto", "Para empleo formal"]
    out = mmc_nlp.zeroshot_tint(msgs, cache=str(tmp_path / "z.parquet"))
    assert list(out["message"]) == msgs
    assert out.loc[0, "mmc_category"] == "legal documentation"
    assert out.loc[1, "mmc_category"] == "employment"
    assert (out["conf"] > 0.5).all()
