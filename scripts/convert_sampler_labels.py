# 저장 위치: yesco-ai-engine/scripts/convert_sampler_labels.py (전체 교체)
"""sampler가 내보낸 ai_labels.jsonl → 학습용 labels.jsonl 정규화 (다운로드 URL 보강)"""
import sys, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data.sap_loader import build_download_url
from src.labeling.schema import TRAINABLE_LABELS

TRAINABLE = {l.value for l in TRAINABLE_LABELS}

def convert(in_jsonl: Path, out_jsonl: Path):
    rows = [json.loads(l) for l in open(in_jsonl, encoding="utf-8") if l.strip()]
    out, skipped = [], 0
    for r in rows:
        label = r.get("label", "")
        if label not in TRAINABLE:      # UNCLEAR/EXCLUDED 등 학습 제외
            skipped += 1
            continue
        url = r.get("download_url") or build_download_url(
            r.get("image_path", ""), r.get("image_name", ""))
        if not url:
            skipped += 1
            continue
        out.append({**r, "download_url": url})

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    import pandas as pd
    dist = pd.Series([r["label"] for r in out]).value_counts().to_dict()
    print(f"학습 라벨: {len(out)}건 (제외 {skipped}건) → {out_jsonl}")
    print(f"클래스 분포: {dist}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("in_jsonl", help="sampler가 만든 ai_labels.jsonl")
    ap.add_argument("--out", default="data/labels/labels.jsonl")
    a = ap.parse_args()
    convert(Path(a.in_jsonl), Path(a.out))
