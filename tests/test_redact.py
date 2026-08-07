import pytest
from sami import redact


def test_self_identification_frames_are_detected():
    for text in ["me llamo maria y necesito ayuda",
                 "hola, mi nombre es jose luis",
                 "soy Carolina y vivo aqui",
                 "hable con la señora Ramirez"]:
        assert redact.has_self_identification(text), text


def test_nationality_words_are_not_treated_as_names():
    # "soy <Capitalised>" is the drop rule, but these are adjectives, not
    # people. Without the allowlist the rule guts the sample for no safety gain.
    for text in ["soy Venezolana y llegue hace un mes",
                 "soy Colombiano por nacimiento"]:
        assert not redact.has_self_identification(text), text


def test_scrub_drops_a_self_identifying_message_rather_than_redacting_it():
    # THE load-bearing assertion. A future edit that "improves" this into a
    # redaction would ship the name pattern we cannot reliably detect.
    out, changed = redact.scrub("me llamo maria y necesito ayuda", nlp=None)
    assert out is None
    assert changed is False


def test_scrub_drops_a_message_carrying_a_phone_number():
    out, _ = redact.scrub("mi numero es 3123456789 llamenme", nlp=None)
    assert out is None


def test_scrub_drops_a_whatsapp_handle():
    out, _ = redact.scrub("escribeme a whatsapp: por favor", nlp=None)
    assert out is None


def test_scrub_passes_clean_text_through_unchanged():
    text = "necesito ayuda con la apostilla del registro de nacimiento"
    out, changed = redact.scrub(text, nlp=None)
    assert out == text
    assert changed is False


def test_scrub_replaces_a_person_entity_when_ner_finds_one():
    class _Ent:
        def __init__(self, t, label): self.text, self.label_ = t, label

    class _Doc:
        ents = [_Ent("Andrea", "PER")]

    class _Nlp:
        def __call__(self, text): return _Doc()

    out, changed = redact.scrub("hable con Andrea en la oficina", nlp=_Nlp())
    assert out == f"hable con {redact.NAME_PLACEHOLDER} en la oficina"
    assert changed is True


def test_scrub_keeps_locations_and_organisations():
    class _Ent:
        def __init__(self, t, label): self.text, self.label_ = t, label

    class _Doc:
        ents = [_Ent("Cucuta", "LOC"), _Ent("Cruz Roja", "ORG")]

    class _Nlp:
        def __call__(self, text): return _Doc()

    text = "fui a Cucuta y me atendio la Cruz Roja"
    out, changed = redact.scrub(text, nlp=_Nlp())
    assert out == text
    assert changed is False


def test_scrub_handles_empty_and_none():
    assert redact.scrub("", nlp=None)[0] is None
    assert redact.scrub(None, nlp=None)[0] is None
