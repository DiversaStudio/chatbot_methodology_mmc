import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import mmc_text as t

def test_split_drops_undefined_and_blanks():
    assert t.split_messages("hola\n\nquiero ppt\nundefined") == ["hola", "quiero ppt"]

def test_split_none_returns_empty():
    assert t.split_messages(None) == []

def test_max_consecutive_similarity_identical():
    emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    assert abs(t.max_consecutive_similarity(emb) - 1.0) < 1e-6

def test_max_consecutive_similarity_single_row():
    assert t.max_consecutive_similarity(np.array([[1.0, 0.0]])) == 0.0

def test_count_reformulations():
    emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    assert t.count_reformulations(emb, threshold=0.9) == 2
