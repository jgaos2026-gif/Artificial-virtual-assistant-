"""Total raw-byte budget for the COLD JSONL reader (defect #4).

max_records * max_line_bytes alone permits ~105 GB at the defaults; these
tests pin that max_total_bytes bounds what is read and that hitting it can
never be reported as a complete or verified inspection.
"""
import json
import tracemalloc

import pytest

from ava_military.braid_reader_adapter import _read_jsonl, read_braided_stream
from test_memory_braid_unanchored import setup_auth

LINE = b'{"a":1}\n'  # 8 bytes


def test_file_over_total_budget_is_incomplete(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(LINE * 100)  # 800 bytes
    records, complete, omitted, diags = _read_jsonl(p, max_total_bytes=400)
    assert len(records) == 50
    assert not complete
    assert any("total byte budget" in d for d in diags)


def test_many_valid_lines_exceeding_combined_budget(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(LINE * 10_000)
    records, complete, _, _ = _read_jsonl(p, max_line_bytes=1024, max_total_bytes=8 * 1000)
    assert len(records) == 1000 and not complete


def test_cutoff_mid_record_never_parses_the_fragment(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(b'{"a":1}\n{"bb":22}\n')
    records, complete, _, diags = _read_jsonl(p, max_total_bytes=12)
    assert records == [{"a": 1}]
    assert not complete
    assert any("cut off by byte budget" in d for d in diags)
    assert not any("malformed" in d for d in diags)


def test_malformed_record_just_before_cutoff_is_still_reported(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(b'{"a":1}\nNOTJSON\n{"c":3}\n')
    records, complete, _, diags = _read_jsonl(p, max_total_bytes=16)
    assert records[0] == {"a": 1} and "_malformed" in records[1]
    assert not complete
    assert any("malformed" in d for d in diags) and any("total byte budget" in d for d in diags)


def test_one_oversized_line_with_budget(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(b'{"x":"' + b"y" * 5000 + b'"}\n')
    records, complete, _, _ = _read_jsonl(p, max_line_bytes=100, max_total_bytes=1000)
    assert records == [] and not complete


def test_file_exactly_at_budget_is_not_false_truncation(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(LINE * 10)
    records, complete, omitted, diags = _read_jsonl(p, max_total_bytes=80)
    assert len(records) == 10 and complete and omitted == 0 and not diags


@pytest.mark.parametrize("bad", [0, -1, 1.5, "10", True])
def test_budget_must_be_a_positive_int(tmp_path, bad):
    p = tmp_path / "cold.jsonl"; p.write_bytes(LINE)
    with pytest.raises(ValueError):
        _read_jsonl(p, max_total_bytes=bad)


def test_budget_hit_cannot_be_reported_as_verified(tmp_path):
    records, snap, baseline, cp, classifier = setup_auth(tmp_path)
    p = tmp_path / "cold.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    kwargs = dict(classifier=classifier, snapshot=snap, baseline=baseline, checkpoint=cp)

    full = read_braided_stream(p, **kwargs)
    assert full.inspection_complete

    cut = read_braided_stream(p, max_total_bytes=p.stat().st_size - 5, **kwargs)
    assert cut.inspection_complete is False
    assert cut.cold_evidence_verified is False
    assert cut.omitted_count_exact is False


def test_peak_memory_is_bounded_by_budget_not_file_size(tmp_path):
    p = tmp_path / "cold.jsonl"; p.write_bytes(LINE * (2 * 1024 * 1024))
    budget = 256 * 1024
    tracemalloc.start()
    try:
        records, complete, _, _ = _read_jsonl(p, max_records=10**9, max_total_bytes=budget)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert not complete
    assert len(records) == budget // len(LINE)
    assert peak < 32 * budget, f"peak {peak} bytes"


def test_view_and_report_agree_on_omitted_exactness_for_any_incomplete_read(tmp_path):
    records, snap, baseline, cp, classifier = setup_auth(tmp_path)
    p = tmp_path / "cold.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n" + '{"long":"' + "x" * 200 + '"}\n')
    view = read_braided_stream(p, classifier=classifier, snapshot=snap, baseline=baseline,
                               checkpoint=cp, max_line_bytes=150)
    assert view.inspection_complete is False
    assert view.omitted_count_exact is False
    assert view.omitted_count_exact == view.report.omitted_count_exact
