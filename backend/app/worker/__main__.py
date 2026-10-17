"""Tek worker döngüsü: jobs tablosundan sıradaki işi alır ve işler.

Henüz uygulanmadı. Plan: SELECT ... WHERE status='queued' ORDER BY priority, created_at;
durumu kalıcı güncelle (transcribing/generating/synthesizing/evaluating), hata olursa
retryable bilgisiyle error'a çek.
"""

if __name__ == "__main__":
    raise SystemExit("worker henüz uygulanmadı")
