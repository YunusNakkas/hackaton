# S0 spike sonuçları

Tarih: 17 Ekim 2026. Script: `eval/s0/spike_transformers.py`. Ham çıktı: `var/s0-results/` (git dışı).

## Ortam

| | |
|---|---|
| Donanım | MacBook Air M5, 16 GB birleşik bellek, fansız |
| Runtime | Transformers 5.20.1, torch 2.14.1, MPS, `device_map="mps"` |
| Model | `google/gemma-4-E2B-it`, bf16, 10,2 GB |
| Ses seti | 10 sentetik Türkçe cümle (macOS Yelda TTS, 16 kHz) |

## Sonuçlar

| Ölçüm | Sonuç | Not |
|---|---|---|
| Yükleme | 5,8 sn | Diskten, önbellek sıcak |
| GPU belleği | 10,2 GB | Yüklemeden sonra sistemde **1,8 GB** boş kaldı |
| İlk çağrı (ısınma) | 17,7 sn | Servis açılırken bir kez boş çağrı yapılmalı |
| ASR süresi | medyan 0,99 sn / klip | 3–5 sn'lik kliplerde |
| ASR WER / CER | **%18,2 / %5,1** | Sentetik ses, gerçek mikrofonda daha kötü olacak |
| Müşteri cevabı | medyan 0,94 sn, 19 tok/s | 15–18 token, rolde kaldı |
| Değerlendirme | medyan 35 sn, 665–780 token | Tek çağrı, 4 boyut |
| JSON geçerliliği | 3/3 | Onarım gerekmedi |
| Kanıt alıntıları | 13/13 birebir, hepsi çalışan turu | |
| Puan tutarlılığı | ±1 sapma | temperature=1.0 ile: empathy 2/3/3, policy 3/4/4, solution 2/2/2, clarity 3/4/3 |

Tahmini tur süresi (çalışan konuşmayı bitirdikten sonra): ASR ~1 sn + cevap ~1 sn + TTS + ağ ≈ **3–4 sn**. TTS henüz ölçülmedi.

## Bulgular

1. **Gemma 4 E2B, Transformers+MPS ile ASR yapabiliyor.** MLX'e şimdilik gerek yok; planın ilk adayı çalışıyor.
2. **ASR hataları anlamı bozabiliyor:** "iade" → "ya da", "kayıt" → "kayıp", "kart ekstrem" → "Kartex Prime". Değerlendirme yanlış transkripte dayanabilir. Önlemler:
   - Yönetici incelemesinde ses dinleme P0'da zaten var.
   - Çalışan turundan sonra transkript ekranda gösterilmeli.
   - ASR prompt'una senaryo sözlüğü (iade, fiş, ekstre…) eklenmeli; bunun etkisi ölçülecek.
3. **Bellek sınırda.** Model yüklüyken 1,8 GB boş kaldı, swap 4,7 GB kullanılıyordu. Backend, tarayıcı ve TTS ile birlikte demo sırasında yavaşlama riski var. İlk `device_map="auto"` denemesi bellek az göründüğü için katmanları diske taşıdı ve çöktü. Servis `device_map="mps"` ile yüklenmeli.
4. **Değerlendirme 35 sn sürüyor.** Bu, polling'li iş akışına uygun; kullanıcı rapor ekranında beklerken ilerleme durumu görmeli.
5. **Puanlarda ±1 sapma var.** Değerlendirmede daha düşük temperature denenmeli. Bu deterministik veya doğru sonuç garantisi vermez; offline tutarlılık testiyle ölçülecek.
6. **Ses girişi en fazla 30 sn** (model kartı). Sözleşme v0.1.1 bu sınıra göre güncellendi.

## Karar

- **P0 modeli:** `gemma-4-E2B-it`, bf16, Transformers+MPS.
- **Yedek:** bellek sorunu demoda tekrarlarsa resmî 4-bit QAT sürümü (`gemma-4-E2B-it-qat-*` / E4B GGUF 6,1 GB) ölçülecek.
- **E4B bf16 (16 GB) ve 12B bu makinede kullanılamaz.**

## Uçtan uca deneme (gerçek model + Yelda TTS)

`eval/e2e_real.py`: çalışan sesi Yelda ile `audio/mp4` (Safari biçimi) üretilip API'ye yüklendi; worker gerçek Gemma ile işledi.

| Adım | Süre |
|---|---|
| Açılış sesi (TTS) | 0,9–1,1 sn |
| Tur (ASR + cevap + TTS), sıcak | 3,6–6,1 sn |
| Tur, ilk sesli istek (yalnız metinle ısınınca) | 27,7 sn → ısınmaya sessiz ses eklendi |
| Tur, boşta bekledikten sonra | **41,8 sn** (ASR tek başına 39,5 sn) |
| Değerlendirme (1130 token) | 54 sn |

Bulgular:
1. **Swap sorunu:** Model boşta kalınca ağırlıkların bir kısmı swap'e gidiyor (swap 6,3 GB, boş bellek ~0,9 GB). Aynı ASR çağrısı 8 kez art arda: ilk çağrı 14 sn, sonrakiler 0,8 sn. Çalışan her turdan önce konuşacağı için bu gecikme gerçek kullanımda tekrarlanabilir. **4-bit model bu makinede P0 ihtiyacı haline geldi.**
2. **Kanıt doğrulaması işe yaradı:** model bir koşuda müşteri cümlesini çalışan kanıtı olarak gösterdi; rapor `unverified_evidence` ile `needs_review` oldu.
3. **ASR sözlük ipucu "kayıt → kayıp" hatasını düzeltmedi.** Başka yaklaşım (ör. senaryo bağlamını prompt'a eklemek) denenecek.
4. Müşteri personası rolünde kaldı ve politikayı zorladı ("Üç iş günü çok uzun").

## Sırada

- [ ] Gerçek mikrofon kayıtlarıyla ASR (5–10 kayıt, farklı kişiler)
- [ ] ASR prompt'una senaryo sözlüğü ekleme etkisi
- [ ] ElevenLabs Türkçe TTS gecikmesi ve kalitesi
- [ ] Değerlendirmede temperature 0,3 ile tutarlılık
- [ ] 15 tur art arda ısınma/yavaşlama testi
- [ ] **4-bit sürümün bellek/kalite karşılaştırması (öncelikli: swap sorunu)**
