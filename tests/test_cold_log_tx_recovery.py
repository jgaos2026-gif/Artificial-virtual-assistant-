from ava_military.cold_log_tx import TransactionalColdLog
import json
def test_transactional_cold_log_appends_durable_jsonl(tmp_path):
    path=tmp_path/"cold.jsonl"; log=TransactionalColdLog(path)
    log.append({"id":"one","value":1})
    log.append({"id":"two","value":2})
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    assert rows==[{"id":"one","value":1},{"id":"two","value":2}]
def test_transactional_cold_log_guard_is_context_manager(tmp_path):
    log=TransactionalColdLog(tmp_path/"cold.jsonl")
    with log._exclusive_guard(): pass
