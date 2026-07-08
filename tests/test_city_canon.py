import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_data


def test_city_canon_variants():
    assert mmc_data.city_canon("Bogota") == "Bogotá"
    assert mmc_data.city_canon("bogotá") == "Bogotá"
    assert mmc_data.city_canon("Soacha Cundinamarca") == "Soacha"
    assert mmc_data.city_canon("Cucuta") == "Cúcuta"
    assert mmc_data.city_canon("Medellín") == "Medellín"
    assert mmc_data.city_canon("Colombia") == "Otra"
    assert mmc_data.city_canon("Cundinamarca") == "Otra"
    assert mmc_data.city_canon(None) == "Otra"
