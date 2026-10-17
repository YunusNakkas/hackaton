#!/bin/sh
# S0 sentetik Türkçe test seslerini üretir: var/s0-audio/<id>.wav (16 kHz mono PCM).
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/var/s0-audio"
mkdir -p "$OUT"
python3 -c "
import json, sys
for it in json.load(open('$ROOT/data/audio_test_manifest/s0_synthetic_tr.json'))['items']:
    print(it['id'] + '\t' + it['text'])
" | while IFS="$(printf '\t')" read -r id text; do
  say -v Yelda -o "$OUT/$id.aiff" "$text"
  afconvert -f WAVE -d LEI16@16000 -c 1 "$OUT/$id.aiff" "$OUT/$id.wav"
  rm "$OUT/$id.aiff"
done
ls "$OUT"
