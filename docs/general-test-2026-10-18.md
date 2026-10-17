# Genel test — 18 Ekim 2026

Ana uygulama: `http://127.0.0.1:5173`. Gerçek model: `gemma4-e2b-text:latest`, Ollama, yerel GPU.

Veri oluşturan ve hata enjekte eden tarayıcı testleri ayrı SQLite veritabanında, `5174` / `8001` test sunucularında yapıldı. Ana uygulamadaki kullanıcılar, eğitimler ve raporlar test için değiştirilmedi.

## Otomatik kontroller

| Kontrol | Sonuç |
| --- | --- |
| Backend `python -m pytest -q --tb=short` | 72 başarılı, 1 atlandı |
| Model servisi `python -m pytest -q` | 7 başarılı |
| Frontend `npm run build` | TypeScript ve üretim derlemesi başarılı |
| `git diff --check` | Başarılı |
| Eski uygulama DB'sinde idempotent seed | Mevcut hesaplarla çakışmadan başarılı |
| API, model servisi ve worker | Health başarılı, worker `model=real` |

Atlanan test macOS `say` ses üretimi testi. Bu Windows kurulumu yazılı prova ve `TTS=none` kullanıyor. Bağımlılıklardan gelen Starlette/HTTPX ve Zod/Rollup uyarıları test veya derleme hatası oluşturmadı.

## Tarayıcıda doğrulanan akışlar

- Geçersiz e-posta ve yanlış şifre için hata gösterimi.
- Yönetici ve çalışan girişi, doğru yönlendirme, çıkış.
- Çalışanın `/admin` sayfasına erişiminin engellenmesi.
- Yönetici genel bakış sayılarının atama ve oturum sonrası güncellenmesi.
- Eğitim kartından önceden seçilmiş eğitimle toplu atama; çalışan sayılarının güncellenmesi.
- Çalışan araması ve detay ekranındaki atamaların doğru görünmesi.
- Çalışanın atanmış eğitimi açması, prova başlatması, Enter ve düğmeyle mesaj göndermesi.
- Gerçek Gemma ile iki yazışma turu; işlem sürerken gönderme/bitirme kontrollerinin kapanması.
- Oturum bitirme, gerçek modelden değerlendirme ve konuşma kanıtlarının görüntülenmesi.
- Ayrı DB'de oluşturulan geçici model hatasının gösterilmesi; arayüzden yeniden deneme ve başarılı rapora dönüş.
- Yönetici onayı, inceleme notunun raporda görünmesi, bekleyen inceleme uyarısının kalkması.
- Yönetici görünümünde konuşan çalışanın gerçek adının kullanılması.
- Açık mavi/lacivert tema geçişi ve yenileme sonrası seçimin korunması.
- Gerçek modelle eğitim taslağı üretimi ve hata sonrası yeniden üretim.
- İstenen 1 senaryonun doğrulanması, taslak başlığını düzenleme, sürümün 2'ye çıkması ve tam 1 eğitimin kataloğa yayımlanması.

Çalışan oluşturma/pasifleştirme, organizasyonlar arası erişim, filtreler, sayfalama, inceleme puan düzeltmeleri, taslak sürüm çakışmaları ve yayımlama davranışı backend testlerinde kapsandı. Bu tur masaüstü uygulama ve yerel tarayıcı üzerinde yapıldı; ayrı mobil cihaz veya yük testi yapılmadı.

## Bulunan ve giderilen sorunlar

1. **Eski DB ile seed çakışması:** Önceki `Demo İşletme` kaydı tanınmadığı için aynı e-postalar yeniden oluşturuluyordu. Eski işletme yeniden kullanılıyor; hesaplar, şifreler ve eğitimler korunuyor. Regresyon testi eklendi.
2. **Yanlış senaryo sayısının kabulü:** Gerçek model bir senaryo isteğine iki senaryo üretebildi. Fazla senaryolar istenen sayıyla sınırlanıp yöneticiye açıklama gösteriliyor. Eksik sayıda üretim için modelden düzeltme isteniyor; eksik çıktı düzelmezse yeniden denenebilir hata oluyor. Üç regresyon testi eklendi.
3. **Değerlendirme hatasından dönüş eksikliği:** Yeniden denenebilir değerlendirme hatasına yeniden başlatma düğmesi eklendi; gerçek modelle tekrar üretim test edildi.
4. **İnceleme sonrası yanlış bekleme metni:** Yönetici onayından sonra kalan uyarı ve üst durum metni düzeltildi. İsteğe bağlı incelemeler ayrı etiketleniyor.
5. **Teknik rapor bayrakları:** `unknown_policy_ref` gibi kodlar Türkçe açıklamalara çevrildi.
6. **Mesaj ve canlı durum sınır durumları:** Başarısız gönderimden sonra metin değişirse yeni istek kimliği kullanılıyor; bekleyen iş yüklenirken yeni gönderim engelleniyor. Aktif oturumlar yenileniyor; iş durumu alınamazsa yeniden kontrol seçeneği var.
7. **Atama görünümünde eski sayılar:** Aktif çalışan seçme listesinin önbelleği de atama sonrası yenileniyor.

Model raporları doğrulanamayan kanıt veya politika atfında yönetici incelemesine yönlendiriliyor. Testte bu koruma çalıştı; uygulamanın çalışması, modelin her puan veya gerekçesinin doğru olduğu anlamına gelmez.
