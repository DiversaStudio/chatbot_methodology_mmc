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
        def __init__(self, t, label, start, end):
            self.text, self.label_ = t, label
            self.start_char, self.end_char = start, end

    class _Doc:
        def __init__(self, ents):
            self.ents = ents

    class _Nlp:
        def __init__(self, ents):
            self._ents = ents

        def __call__(self, text):
            return _Doc(self._ents)

    text = "hable con Andrea en la oficina"
    start = text.index("Andrea")
    ents = [_Ent("Andrea", "PER", start, start + len("Andrea"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == f"hable con {redact.NAME_PLACEHOLDER} en la oficina"
    assert changed is True


def test_scrub_keeps_locations_and_organisations():
    class _Ent:
        def __init__(self, t, label, start, end):
            self.text, self.label_ = t, label
            self.start_char, self.end_char = start, end

    class _Doc:
        def __init__(self, ents):
            self.ents = ents

    class _Nlp:
        def __init__(self, ents):
            self._ents = ents

        def __call__(self, text):
            return _Doc(self._ents)

    text = "fui a Cucuta y me atendio la Cruz Roja"
    cucuta_start = text.index("Cucuta")
    cruzroja_start = text.index("Cruz Roja")
    ents = [
        _Ent("Cucuta", "LOC", cucuta_start, cucuta_start + len("Cucuta")),
        _Ent("Cruz Roja", "ORG", cruzroja_start, cruzroja_start + len("Cruz Roja")),
    ]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == text
    assert changed is False


def test_scrub_handles_empty_and_none():
    assert redact.scrub("", nlp=None)[0] is None
    assert redact.scrub(None, nlp=None)[0] is None


# --- Fix round 1 regressions -------------------------------------------------

def test_scrub_drops_capitalized_soy_with_lowercase_name():
    # Phone keyboards auto-capitalise the first letter of a message while the
    # typed name stays lowercase. This is exactly that shape: "Soy andrea".
    out, changed = redact.scrub("Soy andrea y vivo aqui", nlp=None)
    assert out is None
    assert changed is False


def test_scrub_drops_third_party_lowercase_mention():
    # No self-identification frame here, and NER (which we skip via nlp=None,
    # but which also relies on capitalisation) would miss lowercase "andrea"
    # too. The third-party regex backstop is what has to catch this.
    out, changed = redact.scrub("hable con andrea en la oficina", nlp=None)
    assert out is None
    assert changed is False


def test_scrub_drops_on_overlapping_entities():
    # NER returning both "Ana" and the containing "Ana Maria Rodriguez" as
    # separate PER spans is a real spaCy behaviour. Naive str.replace on the
    # shorter span first corrupts the text under the longer span and then
    # silently skips it (its exact text no longer appears). The offset-based
    # replacement must instead recognise the overlap and refuse to guess.
    class _Ent:
        def __init__(self, t, label, start, end):
            self.text, self.label_ = t, label
            self.start_char, self.end_char = start, end

    class _Doc:
        def __init__(self, ents):
            self.ents = ents

    class _Nlp:
        def __init__(self, ents):
            self._ents = ents

        def __call__(self, text):
            return _Doc(self._ents)

    text = "hable con Ana Maria Rodriguez hoy"
    big_start = text.index("Ana Maria Rodriguez")
    small_start = text.index("Ana")
    ents = [
        _Ent("Ana", "PER", small_start, small_start + len("Ana")),
        _Ent("Ana Maria Rodriguez", "PER", big_start, big_start + len("Ana Maria Rodriguez")),
    ]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out is None
    assert changed is False
