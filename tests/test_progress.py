"""Stage reporting: the run must stay legible, and a failure must stay attributable."""
import io

import pytest

from sami import progress


def test_duration_formatting_uses_two_units():
    assert progress.fmt_duration(0.4) == "0s"
    assert progress.fmt_duration(42) == "42s"
    assert progress.fmt_duration(252) == "4m12s"
    assert progress.fmt_duration(3780) == "1h03m"


def test_stages_are_numbered_and_timed():
    out = io.StringIO()
    pr = progress.Progress(total=2, stream=out)
    with pr.stage("embedding"):
        pass
    with pr.stage("writing"):
        pass
    text = out.getvalue()
    assert "[1/2] embedding ..." in text
    assert "[2/2] writing ..." in text
    assert text.count("done in") == 2


def test_label_prints_before_the_work_so_a_hang_is_identifiable():
    """A stage that never returns must already have announced itself."""
    out = io.StringIO()
    pr = progress.Progress(total=1, stream=out)
    with pr.stage("slow thing"):
        assert "slow thing ..." in out.getvalue()


def test_failure_marks_the_stage_and_reraises():
    out = io.StringIO()
    pr = progress.Progress(total=1, stream=out)
    with pytest.raises(ValueError):
        with pr.stage("embedding"):
            raise ValueError("boom")
    assert "[1/1] embedding FAILED after" in out.getvalue()


def test_can_be_silenced():
    out = io.StringIO()
    pr = progress.Progress(total=1, stream=out, enabled=False)
    with pr.stage("quiet"):
        pass
    pr.note("also quiet")
    assert out.getvalue() == ""
