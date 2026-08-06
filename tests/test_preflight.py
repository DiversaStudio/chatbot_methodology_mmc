"""Preflight checks: each one must catch its failure AND explain the fix.

A check that fails without an actionable `fix` is worse than no check, so the
contract is asserted here rather than trusted.
"""
import pandas as pd
import pytest

from sami import preflight, schema

REAL_HEADER = ["Name", "Timestamp", "City", "Age", "Messages", "Chat_summary"]


@pytest.fixture
def ctx(tmp_path):
    """A context pointing at nothing."""
    return preflight.Context(
        responses_path=tmp_path / "missing_responses.xlsx",
        meal_path=tmp_path / "missing_meal.xlsx",
        out_dir=tmp_path / "out",
    )


def _write_export(path, header=REAL_HEADER, banner=2):
    rows = [["banner", None] for _ in range(banner)]
    rows.append(header)
    rows.append(["whatsapp:+570001"] + ["x"] * (len(header) - 1))
    width = max(len(r) for r in rows)
    rows = [r + [None] * (width - len(r)) for r in rows]
    pd.DataFrame(rows).to_excel(path, index=False, header=False)
    return path


def test_context_has_no_skip_nlp_flag():
    """NLP is mandatory: without clustering there is no categorisation to export."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(preflight.Context)}
    assert "skip_nlp" not in fields


# ---- the contract every check must honour -------------------------------------
def test_every_failure_carries_a_fix(ctx):
    """The whole point: no bare failures."""
    for result in preflight.run_all(ctx):
        if result.status == preflight.FAIL:
            assert result.fix, f"check '{result.name}' failed without a fix"
            assert result.detail, f"check '{result.name}' failed without a detail"


def test_run_all_reports_every_check(ctx):
    assert len(preflight.run_all(ctx)) == len(preflight.CHECKS)


def test_a_broken_check_cannot_kill_the_run(ctx, monkeypatch):
    def exploding(_ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(preflight, "CHECKS", (preflight.check_python, exploding))
    results = preflight.run_all(ctx)
    assert results[0].status == preflight.OK
    assert results[1].status == preflight.FAIL
    assert "boom" in results[1].detail


# ---- individual checks --------------------------------------------------------
def test_missing_data_file_fails_with_path_and_fix(ctx):
    result = preflight.check_responses(ctx)
    assert result.status == preflight.FAIL
    assert "missing_responses.xlsx" in result.detail
    assert "--responses" in result.fix


def test_empty_datasets_folder_fails_naming_the_folder_and_a_fix(ctx):
    """The first thing a fresh clone with an empty datasets/ produces:
    responses_path is None (nothing dropped into the folder), not a path
    to a missing file. This is a different branch of _check_export from
    the not-found-on-disk case above."""
    ctx.responses_path = None
    result = preflight.check_responses(ctx)
    assert result.status == preflight.FAIL
    assert "datasets" in result.detail and "responses" in result.detail
    assert "--responses" in result.fix
    assert result.fix.count("fix:") == 0  # render() adds its own "fix:" label
    rendered = preflight.render([result])
    assert rendered.count("fix:") == 1


def test_present_data_file_passes_and_names_header_row(ctx, tmp_path):
    ctx.responses_path = _write_export(tmp_path / "ok.xlsx")
    result = preflight.check_responses(ctx)
    assert result.status == preflight.OK
    assert "header row 2" in result.detail


def test_data_file_missing_a_required_column_fails(ctx, tmp_path):
    short = [c for c in REAL_HEADER if c != "Chat_summary"]
    ctx.responses_path = _write_export(tmp_path / "short.xlsx", header=short)
    result = preflight.check_responses(ctx)
    assert result.status == preflight.FAIL
    assert "Chat_summary" in result.detail + result.fix


def test_salt_failure_warns_that_hashes_will_differ(ctx, monkeypatch):
    monkeypatch.setattr(preflight.config, "get_salt",
                        lambda: (_ for _ in ()).throw(RuntimeError("SAMI_SALT is not set.")))
    result = preflight.check_salt(ctx)
    assert result.status == preflight.FAIL
    # a recipient using their own salt gets different user_ids — say so
    assert "different user_id" in result.fix


def test_output_dir_missing_parent_fails(ctx, tmp_path):
    ctx.out_dir = tmp_path / "no" / "such" / "place"
    assert preflight.check_output_dir(ctx).status == preflight.FAIL


def test_output_dir_creatable_parent_passes(ctx, tmp_path):
    ctx.out_dir = tmp_path / "exports"
    assert preflight.check_output_dir(ctx).status == preflight.OK


def test_cpu_device_warns_but_does_not_block(ctx, monkeypatch):
    """The headline requirement: no GPU is a warning, never a failure."""
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    result = preflight.check_device(ctx)
    assert result.status == preflight.WARN
    assert not result.failed
    assert "gpu" in result.fix  # points at the opt-in CUDA install


def test_cuda_visible_but_no_device_falls_back_to_cpu(ctx, monkeypatch):
    """Regression: with CUDA_VISIBLE_DEVICES="" torch reports is_available()==True
    while device_count()==0, and every later CUDA call raises 'Invalid device id'.
    The device check must degrade to a CPU warning, not blow up."""
    import torch

    from sami import nlp
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 0)
    monkeypatch.setattr(torch.cuda, "get_device_name",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Invalid device id")))
    assert nlp.cuda_usable() is False
    assert nlp.gpu_name() is None
    assert nlp._device() == "cpu"
    result = preflight.check_device(ctx)
    assert result.status == preflight.WARN


def test_python_version_check_passes_here(ctx):
    assert preflight.check_python(ctx).status == preflight.OK


# ---- rendering ----------------------------------------------------------------
def test_render_and_summarize_flag_blocking_problems(ctx):
    results = preflight.run_all(ctx)
    text = preflight.render(results)
    assert "FAIL" in text and "fix:" in text
    assert "FAILED" in preflight.summarize(results)


def test_summarize_reports_clean_run():
    results = [preflight.Result("a", preflight.OK, "fine"),
               preflight.Result("b", preflight.WARN, "slow", "use a gpu")]
    assert "passed" in preflight.summarize(results)
    assert "1 warning" in preflight.summarize(results)


def test_check_entities_ok_on_the_real_registry():
    from sami import preflight
    r = preflight.check_entities(preflight.Context())
    assert r.status == preflight.OK
    assert "entities" in r.detail and "patterns" in r.detail


def test_check_entities_fails_on_a_broken_registry(tmp_path, monkeypatch):
    from sami import config, preflight
    bad = tmp_path / "entities.csv"
    bad.write_text("entity,kind,pattern,notes\nFoo,organisation,\\bfoo\\b,\n",
                   encoding="utf-8")
    monkeypatch.setattr(config, "ENTITIES_OVERRIDE", bad)
    r = preflight.check_entities(preflight.Context())
    assert r.failed
    assert "organisation" in r.detail or "organisation" in r.fix


def test_entities_check_is_registered():
    from sami import preflight
    assert preflight.check_entities in preflight.CHECKS
