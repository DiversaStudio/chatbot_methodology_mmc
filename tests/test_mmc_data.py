# tests/test_mmc_data.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
import mmc_data as d

def test_clean_city_uses_other_when_otra():
    assert d.clean_city("Otra", " bogota ") == "Bogota"

def test_clean_city_keeps_named_city():
    assert d.clean_city("Medellín", None) == "Medellín"

def test_clean_city_otra_without_other_returns_otra():
    assert d.clean_city("Otra", None) == "Otra"

def test_load_responses_shape_and_columns():
    df = d.load_responses()
    assert len(df) == 946
    for col in ["phone", "city_clean", "age_num", "ts", "n_questions"]:
        assert col in df.columns
    assert df["phone"].str.fullmatch(r"\d+").all()
    assert df["ts"].notna().mean() > 0.9

def test_load_meal_renamed_columns():
    m = d.load_meal()
    assert len(m) == 78
    for col in ["phone", "utility", "would_recommend", "recommendation", "heard_channel"]:
        assert col in m.columns
