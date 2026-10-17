import heapq
import itertools
import threading
from collections.abc import Iterator
from contextlib import contextmanager


class PriorityLock:
    """Tek slotlu kilit; bekleyenler arasında küçük öncelik değeri önce alır, eşitse geliş sırası.

    Çalışan bir üretim kesilmez: değerlendirme sürerken gelen tur cevabı onun bitmesini bekler
    ama kuyruktaki diğer değerlendirmelerin önüne geçer.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._held = False
        self._waiting: list[tuple[int, int]] = []
        self._seq = itertools.count()

    @contextmanager
    def acquire(self, priority: int) -> Iterator[None]:
        ticket = (priority, next(self._seq))
        with self._cond:
            heapq.heappush(self._waiting, ticket)
            while self._held or self._waiting[0] != ticket:
                self._cond.wait()
            heapq.heappop(self._waiting)
            self._held = True
        try:
            yield
        finally:
            with self._cond:
                self._held = False
                self._cond.notify_all()
