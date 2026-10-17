import threading
import time

from app.priority_lock import PriorityLock


def test_waiters_are_served_by_priority_then_arrival():
    lock, order = PriorityLock(), []
    holding = threading.Event()

    def holder():
        with lock.acquire(10):
            holding.set()
            time.sleep(0.2)

    def waiter(name, prio):
        with lock.acquire(prio):
            order.append(name)

    threads = [threading.Thread(target=holder)]
    threads[0].start()
    holding.wait()
    for name, prio in [("eval-1", 10), ("eval-2", 10), ("turn", 0)]:
        t = threading.Thread(target=waiter, args=(name, prio))
        t.start()
        threads.append(t)
        time.sleep(0.02)
    for t in threads:
        t.join()
    assert order == ["turn", "eval-1", "eval-2"]
