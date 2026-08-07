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

    # Herminia is deliberately NOT in the Layer-2 gazetteer (checked at write
    # time) so this test still isolates Layer 1: with a gazetteer name here
    # (e.g. "Andrea", or "Xiomara" as of fix round 3 — it was added to the
    # gazetteer precisely because a round-1 test had picked it for being
    # absent) the message would now be dropped by Layer 2 before NER ever
    # runs, which is correct behaviour but would defeat the point of this
    # specific test. Whatever name is used here will need to keep being
    # checked against the gazetteer as it grows.
    text = "hable con Herminia en la oficina"
    start = text.index("Herminia")
    ents = [_Ent("Herminia", "PER", start, start + len("Herminia"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == f"hable con {redact.NAME_PLACEHOLDER} en la oficina"
    assert changed is True


def test_gazetteer_placeholder_name_stays_out_of_the_gazetteer():
    # Guards the previous test's premise directly: if "Herminia" ever gets
    # added to _FIRST_NAMES, that NER-isolation test would silently start
    # exercising the wrong code path (Layer 2 drop instead of Layer 1
    # redaction) without failing loudly. This makes the assumption explicit.
    assert not redact.contains_known_first_name("Herminia")


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


# --- Fix round 2 regressions: the first-name gazetteer ----------------------

def test_contains_known_first_name_matches_whole_word_case_insensitive():
    assert redact.contains_known_first_name("hable con andrea ayer")
    assert redact.contains_known_first_name("hable con Andrea ayer")
    assert redact.contains_known_first_name("hable con ANDREA ayer")


def test_contains_known_first_name_does_not_match_substrings():
    # "ana" must not fire inside words that merely contain it.
    for text in ["nos vemos mañana", "toda la semana estuve enferma",
                 "mire por la ventana", "llamo manana temprano"]:
        assert not redact.contains_known_first_name(text), text


def test_scrub_drops_a_lowercase_third_party_name_with_no_frame():
    # No self-identification frame, no third-party frame, no capital letter —
    # the gazetteer is the only layer that can catch this.
    out, changed = redact.scrub("necesito hablar con andrea sobre el tramite", nlp=None)
    assert out is None
    assert changed is False


def test_scrub_drops_regardless_of_name_capitalisation():
    for text in ["hable con andrea", "hable con Andrea", "hable con ANDREA"]:
        out, _ = redact.scrub(text, nlp=None)
        assert out is None, text


def test_scrub_passes_clean_text_with_no_known_name_unchanged():
    text = "necesito ayuda con la apostilla del registro de nacimiento"
    out, changed = redact.scrub(text, nlp=None)
    assert out == text
    assert changed is False


# --- Fix round 3 regressions --------------------------------------------

def test_scrub_drops_a_family_relation_frame_with_a_lowercase_name():
    # The reviewer's PoC: no self-ID frame, no third-party frame, and (before
    # this fix) the name wasn't in the gazetteer either.
    out, changed = redact.scrub("mi hija xiomara esta enferma", nlp=None)
    assert out is None
    assert changed is False


def test_scrub_does_not_drop_a_family_relation_frame_without_a_name():
    # "mi hija tiene 5 anos" must NOT drop: "tiene" is a verb, not a name.
    text = "mi hija tiene 5 anos"
    out, changed = redact.scrub(text, nlp=None)
    assert out == text
    assert changed is False


def test_scrub_does_not_drop_common_verbs_after_family_frames():
    for verb in ["esta", "necesita", "es", "no", "se", "ya", "todavia",
                 "tambien", "nacio", "cumple", "va", "fue", "quiere",
                 "sufre", "padece"]:
        text = f"mi hijo {verb} bien"
        out, changed = redact.scrub(text, nlp=None)
        assert out == text, f"unexpectedly dropped on verb {verb!r}"
        assert changed is False


# --- Fix round 4 regressions: distrust sentence-initial NER false positives -

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


def test_scrub_leaves_sentence_initial_common_word_untouched():
    # This is the measured production failure mode: es_core_news_sm tags
    # the auto-capitalised first word of a phone-typed message as PER.
    text = "Quisiera saber si puedo obtener el ppt por tener hijos colombianos"
    ents = [_Ent("Quisiera", "PER", 0, len("Quisiera"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == text
    assert changed is False


def test_scrub_still_drops_a_sentence_initial_gazetteer_name():
    # This drops via the gazetteer (Layer 2), which runs before Layer 1 NER
    # ever sees the text — so the NER mock here is irrelevant to the
    # outcome.
    text = "Andrea necesita ayuda con el ppt"
    ents = [_Ent("Andrea", "PER", 0, len("Andrea"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out is None
    assert changed is False


def test_scrub_still_redacts_a_mid_sentence_non_gazetteer_name():
    # The useful path must survive: this is not sentence-initial and
    # "Herminia" is not a stoplist word, so it still gets redacted.
    text = "hable con Herminia en la oficina"
    start = text.index("Herminia")
    ents = [_Ent("Herminia", "PER", start, start + len("Herminia"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == f"hable con {redact.NAME_PLACEHOLDER} en la oficina"
    assert changed is True


def test_scrub_leaves_a_stoplist_word_untouched_mid_sentence():
    text = "muchas Gracias por su ayuda"
    start = text.index("Gracias")
    ents = [_Ent("Gracias", "PER", start, start + len("Gracias"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == text
    assert changed is False


# --- Fix round 5 regressions: position alone is not a distrust signal -------

def test_scrub_redacts_a_sentence_initial_name_not_in_gazetteer_or_stoplist():
    # THE load-bearing assertion for this round. "Ingrid" is a genuine name,
    # correctly tagged PER, not in the 400-entry gazetteer and not on the
    # opener stoplist. A prior version of this rule distrusted every
    # sentence-initial PER absent from the gazetteer, which let this name
    # ship unredacted. Position is no longer a signal on its own.
    text = "Ingrid me acompano a la oficina de migracion ayer."
    ents = [_Ent("Ingrid", "PER", 0, len("Ingrid"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == f"{redact.NAME_PLACEHOLDER} me acompano a la oficina de migracion ayer."
    assert changed is True


def test_scrub_redacts_a_name_opening_a_second_sentence():
    # Same failure mode, but after a ". " rather than at text start — the
    # old rule fired on any sentence boundary, not just the first word.
    text = "Hola buenas. Ingrid me acompano a la oficina de migracion ayer."
    start = text.index("Ingrid")
    ents = [_Ent("Ingrid", "PER", start, start + len("Ingrid"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == f"Hola buenas. {redact.NAME_PLACEHOLDER} me acompano a la oficina de migracion ayer."
    assert changed is True


def test_scrub_leaves_a_sentence_initial_stoplist_word_unchanged():
    text = "Quisiera saber como puedo ayudar"
    ents = [_Ent("Quisiera", "PER", 0, len("Quisiera"))]
    out, changed = redact.scrub(text, nlp=_Nlp(ents))
    assert out == text
    assert changed is False
