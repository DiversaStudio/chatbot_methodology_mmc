"""Generate synthetic v2-format exports for the test suite.

Fabricated phone numbers only — these files are committed, so they must never
carry real data. Re-run with:
    .venv/Scripts/python.exe tests/fixtures/make_fixtures.py
"""
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent

USERS_HEADER = [
    "Address", "Subitems", "Created At", "QA Messages", "Language", "consent",
    "nationality", "city", "time_in_city", "gender", "age", "children",
    "destination", "QA Summary", "Escalation Status", "Safety Alert",
    "Registration Status", "nationality (raw)", "Registration Started",
    "Registration Completed", "Attempts", "Drop-off Question", "Last Message At",
    "Is Returning User", "City_other", "Gender_other", "Away_duration",
    "Destination_Country", "Age Ranges", "Questions per user", "Migrated From v1",
]

# (address, subitems, created, messages, lang, consent, nat, city, time_in_city, gender,
#  age, children, dest, summary, escal, safety, regstatus, natraw, regstart,
#  regdone, attempts, dropoff, lastmsg, returning, city_other, gender_other,
#  away, destcountry, agerange, nquestions, migrated)
USERS_ROWS = [
    (571110000001, None, "2026-04-01T10:00:00.000Z", "¿Cómo saco el PPT?\nGracias",
     "es", "Sí", "Venezuela", "Medellín", "Más de 1 año", "Mujer", 30, "Si",
     "Colombia", "#legal documentation", None, None, "Completed", None,
     "2026-04-01T09:58:00.000Z", "2026-04-01T10:00:00.000Z", 1, None,
     "2026-04-01T10:05:00.000Z", None, None, None, "Entre 1 a 5 años",
     "Colombia", "18-35", 2, "v1:1000001"),
    (571110000002, None, "2026-04-02T11:00:00.000Z", "Necesito ayuda humanitaria",
     "es", "Sí", "Venezuela", "Cúcuta", "Menos de 1 mes", "Hombre", 45, "No",
     "Colombia", "humanitarian assistance", None, None, "Completed", None,
     "2026-04-02T10:58:00.000Z", "2026-04-02T11:00:00.000Z", 1, None,
     "2026-04-02T11:05:00.000Z", None, None, None, "Menos de 1 mes",
     "Colombia", "36-50", 1, "v1:1000002"),
    (571110000003, None, "2026-04-03T12:00:00.000Z", "Busco empleo en Bogotá",
     "es", "Sí", "Venezuela", "Otra", "Más de 1 año", "Mujer", 17, "Si",
     "Colombia", "#employment", None, None, "Completed", None,
     "2026-04-03T11:58:00.000Z", "2026-04-03T12:00:00.000Z", 2, None,
     "2026-04-03T12:05:00.000Z", None, "Bogotá", None, "Entre 1 a 5 años",
     "Colombia", "0-17", 1, "v1:1000003"),
    (571110000004, None, "2026-04-04T13:00:00.000Z", None,
     "es", "Sí", "Ecuador", "Medellín", "Más de 1 año", "Prefiero no responder",
     52, "No", "Otro", None, None, None, "Abandoned", None,
     "2026-04-04T12:58:00.000Z", None, 3, "city", None, None, None, None,
     "Hace más de 5 años", "Estados Unidos", "50 and above", None, "v1:1000004"),
    # --- v2-native cohort: no 'Migrated From v1' ---
    (571110000005, None, "2026-07-25T14:00:00.000Z", "¿Dónde hay albergue en Ipiales?",
     "es", "Sí", "Colombia", "Ipiales", "Menos de 1 mes", "Mujer", 28, "Sí",
     "Colombia", "[2026-07-25 14:05] El usuario preguntó sobre albergues en "
     "Ipiales, rutas hacia Medellín y asistencia humanitaria.",
     None, None, "Completed", None, "2026-07-25T13:58:00.000Z",
     "2026-07-25T14:00:00.000Z", 1, None, "2026-07-25T14:10:00.000Z", None,
     None, None, None, "Colombia", None, None, None),
    (571110000006, None, "2026-07-26T15:00:00.000Z", "I need medical help",
     "en", "Sí", "Venezuela", "Bogotá", "Entre 1 y 3 meses", "Trans", 34, "No",
     "Chile", "[2026-07-26 15:05] User asked about medical services in Bogotá.",
     "escalated", "flagged", "Completed", None, "2026-07-26T14:58:00.000Z",
     "2026-07-26T15:00:00.000Z", 1, None, "2026-07-26T15:10:00.000Z", "yes",
     None, None, None, "Chile", None, None, None),
    # Empty-id row: reproduces the null address in the real export, forcing pandas to
    # infer Address column as float64 dtype (nullable numeric type requires at least one NA).
    # Task 4's _read_export() is specified to drop rows with null id, so this tests that path.
    # Include Attempts=0 to keep row non-empty (pandas drops all-null rows).
    (None, None, None, None, None, None, None, None, None, None, None, None,
     None, None, None, None, None, None, None, None, 0, None, None, None, None,
     None, None, None, None, None, None),
]

# Column 2 and 3 are the EMPTY v1 duplicates; 6 and 8 carry the real v2 data.
SURVEY_HEADER = [
    "Respondent", "Recorded At",
    "Ha sido un gusto brindarte información. Para mejorar este servicio, "
    "¿nos podrías indicar qué tan útil fue la información entregada?",
    "¿Cómo conociste este servicio?\n1) Recomendación de otro migrante",
    "¿Recomendarías este servicio a otras personas migrantes?\n1) Sí",
    "¿Tienes alguna recomendación para mejorar este servicio?",
    "Ha sido un gusto brindarte información. Para mejorar este servicio, "
    "¿nos podrías indicar qué tan útil fue la información entregada?\n"
    "1) ⭐ – Nada útil\n5) ⭐⭐⭐⭐⭐ – Muy útil.1",
    "¿Por qué la información entregada no fue útil?",
    "¿Cómo conociste este servicio?\n1) Otro migrante\n2) Recomendación de ONG",
    "Gracias por tu retroalimentación.",
    "v1 Recomendarias", "v1 Medio Otro", "Migrated From v1",
]

SURVEY_ROWS = [
    # respondent, recorded, v1useful, v1disc, v1rec, v1text, useful, why,
    # discovery, thanks, v1recomendarias, v1medio, migrated
    (571110000001, "2026-04-01T10:30:00.000Z", None, None, None, None,
     "Muy útil", "no", "Redes sociales", None, "Sí", None, "v1:1000001"),
    (571110000002, "2026-04-02T11:30:00.000Z", None, None, None, None,
     "Nada útil", "No me recomendaste nada para Cúcuta", "Otro migrante",
     None, "No", None, "v1:1000002"),
    (571110000003, "2026-04-03T12:30:00.000Z", None, None, None, None,
     "Medianamente útil", "te confundiste de ciudad", "Otro", None,
     "Prefiero no responder", "un amigo", "v1:1000003"),
    (571110000005, "2026-07-25T14:30:00.000Z", None, None, None, None,
     "Útil", "Todo bien gracias", "Recomendación de ONG", None, None, None,
     None),
    # Empty-id row: reproduces the null respondent in the real export, forcing pandas to
    # infer Respondent column as float64 dtype. Task 4's _read_export() will drop this.
    # Include a dummy value (0) in Migrated From v1 column to keep row non-empty (pandas drops all-null rows).
    (None, None, None, None, None, None, None, None, None, None, None, None, 0),
]


def _write(path: Path, title: str, header: list, rows: list) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.append([title])                       # banner row 0
    ws.append(["Group Title"])               # banner row 1
    ws.append(header)                        # header row 2
    for r in rows:
        ws.append(list(r))
    wb.save(path)


def main() -> None:
    _write(HERE / "users_v2.xlsx", "users", USERS_HEADER, USERS_ROWS)
    _write(HERE / "survey_v2.xlsx", "survey responses", SURVEY_HEADER, SURVEY_ROWS)
    print(f"wrote {HERE / 'users_v2.xlsx'}")
    print(f"wrote {HERE / 'survey_v2.xlsx'}")


if __name__ == "__main__":
    main()
