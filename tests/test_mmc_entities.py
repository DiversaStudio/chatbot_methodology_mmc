import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_entities as e

def test_extract_ppt_variants():
    assert "PPT" in e.extract_entities("Necesito sacar el ppt")
    assert "PPT" in e.extract_entities("informacion sobre el Permiso por Proteccion Temporal")

def test_extract_institution_accent_insensitive():
    assert "Migración Colombia" in e.extract_entities("fui a migracion colombia")

def test_extract_eps():
    assert "EPS" in e.extract_entities("como me afilio a una EPS")

def test_no_false_positive():
    assert e.extract_entities("hola buenos dias") == set()

def test_entity_counts_orders_desc():
    s = e.entity_counts(["ppt", "ppt y eps", "nada"])
    assert s.loc["PPT"] == 2
    assert list(s.index)[0] == "PPT"
