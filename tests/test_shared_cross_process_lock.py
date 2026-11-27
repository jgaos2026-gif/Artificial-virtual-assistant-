import multiprocessing as mp
import os
from pathlib import Path

from ava_military.shared_cross_process_lock import (
    CrossProcessAdvisoryLock, CrossProcessLockTimeout, lock_path_for,
)
from ava_military.cold_log_tx import TransactionalColdLog


def _lock_worker(path, started, acquired):
    lock = CrossProcessAdvisoryLock(path)
    started.set()
    with lock.exclusive():
        acquired.set()


def _timeout_worker(path, started, result):
    started.set()
    try:
        with CrossProcessAdvisoryLock(path, timeout=0.2, poll_interval=0.01).exclusive():
            result.put("acquired")
    except CrossProcessLockTimeout:
        result.put("timeout")


def _crash_while_holding_lock(path, acquired):
    with CrossProcessAdvisoryLock(path).exclusive():
        acquired.set()
        os._exit(0)


def test_lock_identity_is_canonical_for_reader_and_writer(tmp_path):
    target = tmp_path / "cold.jsonl"
    writer = TransactionalColdLog(target)
    reader_lock = CrossProcessAdvisoryLock(target)
    assert writer._cross_process_lock.path == reader_lock.path == lock_path_for(target)


def test_independent_process_blocks_on_same_lock_until_release(tmp_path):
    target = tmp_path / "cold.jsonl"
    lock = CrossProcessAdvisoryLock(target)
    ctx = mp.get_context("spawn")
    started, acquired = ctx.Event(), ctx.Event()
    proc = ctx.Process(target=_lock_worker, args=(str(target), started, acquired))
    with lock.exclusive():
        proc.start()
        assert started.wait(5), "child did not start"
        assert not acquired.wait(0.25), "child entered while parent held lock"
    assert acquired.wait(5), "child did not acquire after release"
    proc.join(5)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
    assert proc.exitcode == 0


def test_lock_timeout_fails_closed_when_another_process_holds_lock(tmp_path):
    target = tmp_path / "cold.jsonl"
    ctx = mp.get_context("spawn")
    started = ctx.Event()
    result = ctx.Queue()
    proc = ctx.Process(target=_timeout_worker, args=(str(target), started, result))
    with CrossProcessAdvisoryLock(target):
        proc.start()
        assert started.wait(5), "timeout worker did not start"
        assert result.get(timeout=5) == "timeout"
    proc.join(5)
    assert proc.exitcode == 0


def test_kernel_releases_lock_after_holder_crashes_without_cleanup(tmp_path):
    target = tmp_path / "cold.jsonl"
    ctx = mp.get_context("spawn")
    acquired = ctx.Event()
    proc = ctx.Process(target=_crash_while_holding_lock, args=(str(target), acquired))
    proc.start()
    assert acquired.wait(5), "child never acquired lock"
    proc.join(5)
    assert proc.exitcode == 0
    # The persistent lock file remains; the OS lock itself was released on exit.
    with CrossProcessAdvisoryLock(target, timeout=1).exclusive():
        assert True


def _uncooperative_append(path, ready, proceed):
    ready.set()
    if not proceed.wait(5):
        raise RuntimeError("parent did not release uncooperative writer")
    # Deliberately bypass CrossProcessAdvisoryLock.
    with open(path, "ab", buffering=0) as stream:
        stream.write(b'{"intruder":true}\n')
        os.fsync(stream.fileno())


def test_uncooperative_writer_is_detected_by_post_read_currency_check(tmp_path):
    target = tmp_path / "cold.jsonl"
    target.write_bytes(b'{"safe":true}\n')
    before = target.read_bytes()
    ctx = mp.get_context("spawn")
    ready, proceed = ctx.Event(), ctx.Event()
    proc = ctx.Process(target=_uncooperative_append, args=(str(target), ready, proceed))
    proc.start()
    assert ready.wait(5)
    try:
        # Reader owns the cooperative lock, but the adversarial writer ignores it.
        with CrossProcessAdvisoryLock(target).exclusive():
            pre_ok = target.read_bytes() == before
            proceed.set()
            proc.join(5)
            if proc.is_alive():
                proc.terminate()
                proc.join(5)
            post_ok = target.read_bytes() == before
        assert pre_ok is True
        assert post_ok is False
        assert proc.exitcode == 0
    finally:
        proceed.set()
        if proc.is_alive():
            proc.terminate()
            proc.join(5)


def test_writer_appends_with_shared_lock(tmp_path):
    target = tmp_path / "cold.jsonl"
    log = TransactionalColdLog(target)
    log.append({"id": "one"})
    assert target.read_text().endswith("\n")


def _anchored_writer_lock_worker(lock_path, started, acquired):
    from ava_military.anchor import _exclusive_writer_lock
    started.set()
    with _exclusive_writer_lock(Path(lock_path)):
        acquired.set()


def test_shared_lock_interoperates_with_unchanged_anchored_cold_log_lock(tmp_path):
    target = tmp_path / "anchored.jsonl"
    lock_path = target.with_name(target.name + ".writer.lock")
    ctx = mp.get_context("spawn")
    started, acquired = ctx.Event(), ctx.Event()
    proc = ctx.Process(
        target=_anchored_writer_lock_worker,
        args=(str(lock_path), started, acquired),
    )
    with CrossProcessAdvisoryLock(target).exclusive():
        assert lock_path_for(target) == lock_path
        proc.start()
        assert started.wait(5)
        assert not acquired.wait(0.25)
    assert acquired.wait(5)
    proc.join(5)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
    assert proc.exitcode == 0
