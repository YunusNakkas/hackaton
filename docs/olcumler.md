# Ölçümler

Donanım: MacBook Air M5, 16 GB. Model: `mlx-community/gemma-4-e4b-it-4bit` (MLX). Model ve runtime seçimi: `docs/s0-spike.md`.

## Taslak üretimi (yönetici formu → senaryo + rubrik)

Script: `eval/draft_bench.py` — 5 farklı işletme (kafe, eczane, kargo, spor salonu, banka), her biri 2 koşu, gerçek model.
Ham sonuç: `var/draft-bench/{once,sonra}.json` (git dışı).

| | Önce (`draft@1`) | Sonra (`draft@2` + kodda onarım) |
|---|---|---|
| Geçerli taslak | 6/10 | **10/10** |
| İstenen senaryo sayısına uyum | 6/6 | 10/10 (fazla üretilen 2 taslakta kırpıldı, uyarı verildi) |
| Kullanıcı metnine sızan iç kimlik ("Politika_1'e uygun…") | 4 taslak, 6 metin | **0** |
| Medyan süre | 59 sn | **32 sn** |

Geçersiz taslakların hepsi **biçim** hatasıydı, içerik değil:
- anahtar/kimlikte Türkçe karakter (`reçete_sorunu_antibiyotik`, `garanti_sınırlandırma`) — 3 taslak
- rubrik seviyeleri liste yerine sözlük (`{"0": "...", ...}`) — 1 taslak

Düzeltme (`backend/app/services/drafts.py: repair_generated`): kimlikler ASCII'ye çevrilir ve tekilleştirilir, sözlük
seviyeler listeye çevrilir, metindeki politika kimlikleri hal ekiyle birlikte politikanın adıyla değiştirilir
("Politika_1'e" → "'Yanlış sipariş' politikasına"), fazla senaryo kırpılır / eksik senaryo uyarılır. Prompt'a da
aynı kurallar eklendi. Süre düşüşü, onarım çağrısına (ikinci model çağrısı) artık gerek kalmamasından.

**Kalan sorunlar (elle inceleme):** Türkçe çoğunlukla doğal; ancak bazı metinlerde dil bozukluğu var ("Siz var mı
bakınayım", "Kremün iadesi", "ücretsiz olarak ücretsiz", "acaba acaba" tekrarı) ve bazı rubrikler 2 boyutla geliyor
(prompt 3–5 istiyor). Yönetici taslağı yayımlamadan önce düzenler; bu adım bu yüzden zorunlu.

## Gerçek mikrofonla ASR (ön sonuç)

Dahili mikrofonla 5 turluk tek deneme (`var/mic-tests/20261018-000439`, git dışı):
- Konuşmalı 3 turun 2'sinde Gemma transkripti doğru; uzun turda Whisper (large-v3-turbo) ile benzer hatalar.
- Sessiz 2 turda iki model de metin uydurdu → sessiz kayıt artık modele gitmeden reddediliyor (`no_speech`).
- AirPods mikrofonuyla yapılan ilk denemede iki model de anlamsız çıktı verdi (Bluetooth dar bant).

Kapsamlı ölçüm (farklı kişiler, sabit cümleler, WER) henüz yapılmadı.

## "Zorlaştırılmış tekrar" (adaptive) müşteri

Aynı soğuk çalışan cevabına ("Teknik ekip yoğun, bekleyeceksiniz.") odak = empati, 4'er koşu:
- `same`: süre soruyor ("Bu bekleyişin bir tahmini var mı?")
- `adaptive`: duygusunu açıkça söylüyor ("Bu ihmal hissi beni gerçekten çok öfkelendiriyor", "tamamen beni hiçe saymak gibi")

Yönerge prompt'un sonundayken fark zayıftı; ruh hâlinin hemen ardına taşınınca belirginleşti.
