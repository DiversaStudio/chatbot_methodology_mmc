import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_text


def test_emotion_labels():
    clf = mmc_text.load_emotion_pipeline()
    out = clf(["Estoy muy feliz, gracias por la ayuda", "Tengo miedo, me van a deportar"])
    assert len(out) == 2
    assert all(set(o) >= {"label", "score"} for o in out)
    assert all(0.0 <= o["score"] <= 1.0 for o in out)
