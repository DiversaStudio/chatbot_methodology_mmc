import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
import mmc_data


def _fake_df():
    return pd.DataFrame({
        "phone": ["1", "2"],
        "Messages": ["Hola\nQuiero informacion de los servicios", "12\n?\nNecesito ayuda con el PPT urgente"],
        "city_clean": ["Medellín", "Bogotá"],
        "ts": pd.to_datetime(["2026-04-01", "2026-04-02"]),
        "Gender": ["F", "M"],
        "Age Ranges": ["18-25", "26-35"],
        "Nationality": ["Venezuela", "Venezuela"],
        "age_num": [22.0, 30.0],
    })


def test_explode_and_noise_filter():
    msgs = mmc_data.load_messages(_fake_df())
    # user 1: "Hola" (kept, len>=3) + "Quiero..." = 2 msgs
    # user 2: "12" dropped (digits), "?" dropped, "Necesito..." kept = 1 msg
    assert list(msgs["message"]) == [
        "Hola",
        "Quiero informacion de los servicios",
        "Necesito ayuda con el PPT urgente",
    ]
    assert list(msgs["msg_idx"]) == [0, 1, 0]
    assert list(msgs["n_msgs_user"]) == [2, 2, 1]
    assert list(msgs["phone"]) == ["1", "1", "2"]
    assert msgs.loc[0, "city_clean"] == "Medellín"
