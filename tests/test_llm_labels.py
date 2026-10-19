"""LLM label datasets: prompts, batching, synthetic dedupe, agreement, review workbook.

All synthetic: a fake client stands in for `claude -p`, texts are made up, embeddings are hand-built.
Nothing here needs the client's data, the network or the `claude` CLI.
"""
import json

import numpy as np
import pandas as pd
import pytest

from sami import categorize as cz
from sami import llm_labels as ll


def _work(n=12):
    """12 labelled messages per class (4 test, 8 dev) plus unlabelled ones, in 2-message conversations."""
    rows = []
    for c in ll.CLASSES:
        for i in range(n):
            rows.append({"text": f"{c[:5]} mensaje {i:02d}", "label": c, "split": "test" if i < 4 else "dev"})
    rows += [{"text": f"sin etiqueta {i}", "label": None, "split": "unlabeled"} for i in range(6)]
    w = pd.DataFrame(rows)
    w["row"] = np.arange(len(w))
    w["Conversation ID"] = [f"c{i // 2}" for i in range(len(w))]
    w["Message #"] = [i % 2 for i in range(len(w))]
    w["in_na_sheet"] = w["label"] == ll.NONE
    w["context"] = ""
    return w


class FakeClient:
    """Labels every message as `answer` (or per `fn`), counts calls, can fail or hit the limit first."""
    model = "fake"

    def __init__(self, answer=ll.NONE, fail=0, limits=0):
        self.answer, self.fail, self.limits, self.calls = answer, fail, limits, 0

    def __call__(self, system, user, schema):
        self.calls += 1
        if self.limits:
            self.limits -= 1
            raise ll.UsageLimit("limit")
        if self.fail:
            self.fail -= 1
            return {"result": {"items": []}, "usage": {}}
        if "items" in schema["properties"]:
            ids = [json.loads(l)["id"] for l in user.splitlines()[1:]]
            return {"result": {"items": [{"id": i, "c": self.answer} for i in ids]}, "usage": {}}
        n = int(user.split("Write ")[1].split()[0]) if "Write " in user else 25
        return {"result": {"messages": [f"mensaje {self.calls} {k}" for k in range(n)]}, "usage": {}}


def test_prepare_drops_scrubbed_and_builds_context():
    n = 60                                                   # enough rows for the stratified split
    df = pd.DataFrame({
        "row": range(n), "Conversation ID": [f"c{i // 4}" for i in range(n)], "Message #": [i % 4 for i in range(n)],
        "text": [f"mensaje {i}" for i in range(n)],
        "label": [cz.CATEGORIES[i % 2] for i in range(n)], "in_na_sheet": False})
    out = ll.prepare(df, scrub=lambda t: (None, False) if t == "mensaje 1" else (t, False))
    assert pd.isna(out.loc[1, "text"])                       # dropped: never sent
    assert out.loc[2, "context"] == "mensaje 0"              # the dropped message is not context
    assert out.loc[4, "context"] == ""                       # first message of its conversation
    assert out.loc[7, "context"] == "mensaje 4 | mensaje 5 | mensaje 6"      # nothing from another conversation
    assert set(out["split"]) <= {"test", "dev"} and (out["split"] == "test").any()


def test_label_prompt_uses_dev_only_and_all_classes():
    w = _work()
    p = ll.build_label_prompt(w)
    ll.assert_no_test_text(p, w)
    for c in cz.CATEGORIES:
        assert f"- {c}\n" in p
    assert "{" not in p.replace('{"', "")                    # every placeholder was filled


def test_leak_check_fires():
    w = _work()
    test_text = w.loc[w["split"] == "test", "text"].iloc[0]
    with pytest.raises(AssertionError):
        ll.assert_no_test_text(f"examples: {json.dumps(test_text)}", w)


def test_check_labels_rejects_bad_answers():
    ok = {"items": [{"id": 1, "c": ll.NONE}, {"id": 2, "c": "Empleabilidad"}]}
    ll.check_labels(ok, [1, 2])
    for bad, ids in [({"items": ok["items"][:1]}, [1, 2]),
                     ({"items": ok["items"] + [{"id": 3, "c": ll.NONE}]}, [1, 2]),
                     ({"items": [{"id": 1, "c": "inventada"}, {"id": 2, "c": ll.NONE}]}, [1, 2]),
                     ({"items": [{"id": 1, "c": ll.NONE}, {"id": 1, "c": ll.NONE}]}, [1, 2])]:
        with pytest.raises(ValueError):
            ll.check_labels(bad, ids)


def test_batches_resume_retry_and_wait_on_limit(tmp_path):
    w = _work().set_index("row")
    jobs = ll.label_jobs(w, "t_")
    assert len(jobs) == -(-len(w) // ll.LABEL_BATCH)
    waits = []
    c = FakeClient(fail=1, limits=1)
    s = ll.run_batches(jobs, tmp_path, c, "sys", ll.LABEL_SCHEMA, ll.check_labels, workers=1, sleep=waits.append)
    assert s["failed"] == 0 and s["ok"] == len(jobs) and waits == [ll.LIMIT_WAIT]
    calls = c.calls
    again = ll.run_batches(jobs, tmp_path, c, "sys", ll.LABEL_SCHEMA, ll.check_labels, workers=1)
    assert again["skip"] == len(jobs) and c.calls == calls          # finished batches are not asked again
    saved = json.loads((tmp_path / "t_0000.json").read_text())
    assert saved["model"] == "fake" and saved["prompt"] and saved["date"]
    assert len(ll.read_labels(tmp_path)) == len(w)


def test_persistent_bad_answer_leaves_failed_file(tmp_path):
    jobs = ll.label_jobs(_work().set_index("row").iloc[:5], "f_")
    s = ll.run_batches(jobs, tmp_path, FakeClient(fail=99), "sys", ll.LABEL_SCHEMA, ll.check_labels, workers=1)
    assert s["failed"] == 1 and (tmp_path / "f_0000.failed").exists()


def test_synth_jobs_cover_every_class_from_dev_seeds():
    w = _work()
    jobs = ll.synth_jobs(w, {c: 60 for c in ll.CLASSES}, "r0_")
    assert len(jobs) == len(ll.CLASSES) * 3                          # 25 + 25 + 10
    assert sum(j[2]["n"] for j in jobs) == 60 * len(ll.CLASSES)
    test_texts = set(w.loc[w["split"] == "test", "text"])
    assert not any(json.dumps(t) in j[1] for j in jobs for t in test_texts)      # seeds never come from the test set
    none_job = next(j for j in jobs if j[2]["cat"] == ll.NONE)
    assert "no need" in none_job[1]


def test_dedupe_exact_near_and_per_class_limit():
    syn = pd.DataFrame({"text": ["hola uno", "Hola  UNO", "real text", "otro a", "otro b", "cuarto"],
                        "category": ["A", "A", "A", "A", "A", "B"]})
    out = ll.dedupe_synth(syn, ["real text"])
    assert out["text"].tolist() == ["hola uno", "otro a", "otro b", "cuarto"]
    vec = {"hola uno": [1, 0], "otro a": [0.999, 0.04], "otro b": [0, 1], "cuarto": [1, 0]}   # cuarto: other class
    emb = lambda ts: np.array([np.array(vec[t]) / np.linalg.norm(vec[t]) for t in ts])
    near = ll.dedupe_synth(syn, ["real text"], embed=emb)
    assert near["text"].tolist() == ["hola uno", "otro b", "cuarto"]  # "otro a" ~ "hola uno" in class A only
    assert len(ll.dedupe_synth(syn, [], limit=1)) == 2                 # one per class


def test_build_synthetic_refills_to_350_per_class(tmp_path):
    w = _work()
    syn = ll.build_synthetic(w, tmp_path, FakeClient(), "sys", workers=1)
    assert set(syn["category"].value_counts()) == {ll.SYNTH_PER_CLASS}
    assert len(syn) == ll.SYNTH_PER_CLASS * len(ll.CLASSES)


def test_agreement_on_a_hand_made_confusion():
    r = ll.agreement(["Empleabilidad"] * 3 + [ll.NONE], ["Empleabilidad", "Empleabilidad", ll.NONE, ll.NONE])
    assert r["n"] == 4 and r["accuracy"] == 0.75 and r["share_ninguna"] == 0.5
    assert r["report"].loc["Empleabilidad", "recall"] == pytest.approx(2 / 3)


def test_review_workbook_layout(tmp_path):
    from openpyxl import load_workbook
    w = _work()
    pred = {int(r): ("Empleabilidad" if r % 3 == 0 else c) for r, c in zip(w["row"], w["label"].fillna(ll.NONE))}
    syn = pd.DataFrame({"text": ["a", "b"], "category": ["Emprendimiento", "Riesgos de protección"]})
    path = tmp_path / "out.xlsx"
    ll.write_review_workbook(path, w, pred, syn, {0: "Emprendimiento", 1: ll.NONE}, {"Mensajes": 1}, today="2026-10-16")
    wb = load_workbook(path)
    assert wb.sheetnames == ["Guia_revision", "Etiquetas", "Sinteticos", "_listas"]
    assert wb["_listas"].sheet_state == "hidden"
    hdr = [c.value for c in wb["Etiquetas"][1]]
    assert hdr[:5] == ["Contexto (3 mensajes previos)", "Mensaje", "Etiqueta cliente", "Etiqueta LLM", "Validación humana"]
    assert len(wb["Etiquetas"].data_validations.dataValidation) == 2
    assert wb["Sinteticos"]["G2"].value == "sí"                       # the mismatch is listed first
    assert ll.MODEL in wb["Guia_revision"]["A3"].value


def test_module_imports_and_help_without_claude(capsys):
    with pytest.raises(SystemExit) as e:
        ll.main(["--help"])
    assert e.value.code == 0 and "prep" in capsys.readouterr().out


def test_labels_table_mirrors_first_pass_columns():
    w = _work()
    pred = {int(r): ll.NONE for r in w["row"]}
    t = ll.labels_table(w, pred)
    assert list(t.columns[:12]) == ["Contexto (3 mensajes previos)", "Mensaje", "Etiqueta cliente", "Etiqueta LLM",
                                    "Validación humana", "Categoría corregida", "Comentario", "Fuente", "split",
                                    "id", "Conversation ID", "Message #"]
    assert set(t["split"]) == {"prueba", "entrenamiento", "sin etiqueta"}
    assert (t.loc[t["Etiqueta cliente"] == ll.NONE, "Coincide cliente"] == "sí").all()
    assert (t.loc[t["Etiqueta cliente"].isna(), "Coincide cliente"] == "").all()


def test_labels_xlsx_has_filter_dropdowns_and_shading(tmp_path):
    from openpyxl import load_workbook
    w = _work()
    pred = {int(r): "Empleabilidad" for r in w["row"]}
    t = ll.labels_table(w, pred)
    ll.write_labels_xlsx(tmp_path / "t.xlsx", t)
    ws = load_workbook(tmp_path / "t.xlsx")["Etiquetas"]
    assert ws.auto_filter.ref.endswith(str(len(t) + 1)) and ws.freeze_panes == "A2"
    assert len(ws.data_validations.dataValidation) == 2
    assert ws.cell(2, 1).fill.fgColor.rgb == "00FFF2CC"
