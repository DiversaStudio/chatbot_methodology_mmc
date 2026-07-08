import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import mmc_text


def test_is_courtesy():
    assert mmc_text.is_courtesy("Hola")
    assert mmc_text.is_courtesy("Muchas gracias, Dios le bendiga")
    assert mmc_text.is_courtesy("buenos días")
    assert mmc_text.is_courtesy("AMÉN 🙏")
    assert not mmc_text.is_courtesy("Necesito ayuda con el PPT")
    assert not mmc_text.is_courtesy("Cómo solicitar el salvoconducto")


def test_stopwords_present():
    assert "de" in mmc_text.SPANISH_STOPWORDS
    assert "gracias" in mmc_text.SPANISH_STOPWORDS
