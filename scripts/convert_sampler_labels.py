# 저장 위치: yesco-ai-engine/scripts/convert_sampler_labels.py
"""
sampler(YESCO 실사추출기) 결과 → AI 엔진 학습용 라벨 JSON 변환

입력: 점검결과확인서.xlsx  (NO, 고객센터명, 주소, 세대번호, 구분, 결과, 확인 요청사항, 상세판정)
      + (선택) 원본 SAP df — 이미지 경로/파일명, 부적합항목을 얻기 위함

출력: data/labels/labels.jsonl        (확정된 학습 라벨)
      data/labels/_needs_review.csv   (사람이 5클래스 세분을 마저 찍어야 하는 건)
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.labeling.schema import from_sampler, NEEDS_REVIEW, Label, urgency_of
from src.data.sap_loader import load_sap_excel, build_download_url


def convert(verdict_xlsx: Path, sap_xlsx: Path | None, out_dir: Path, labeler: str):
    out_dir.mkdir(parents=True, exist_ok=True)

    vdf = pd.read_excel(verdict_xlsx, dtype=str).fillna("")
    # 컬럼 이름 유연 처리 (sampler col_map 기준)
    col_result = _find(vdf, ["결과"])
    col_verdict = _find(vdf, ["상세판정", "판정"])
    col_order = _find(vdf, ["오더번호", "오더", "order_no", "세대번호"])  # 최후 fallback

    # 원본 SAP: 이미지/부적합항목 정보 결합
    sap = None
    if sap_xlsx and Path(sap_xlsx).exists():
        sap = load_sap_excel(sap_xlsx)
        sap["order_no"] = sap["order_no"].astype(str).str.strip()

    labels, review = [], []
    for _, r in vdf.iterrows():
        verdict = r.get(col_verdict, "") if col_verdict else ""
        result = r.get(col_result, "") if col_result else ""

        # 원본 SAP에서 이 건의 이미지/부적합항목 찾기
        img_name = img_path = defect_item = ""
        order = str(r.get(col_order, "")).strip() if col_order else ""
        if sap is not None and order:
            hit = sap[sap["order_no"] == order]
            if len(hit):
                row0 = hit.iloc[0]
                img_name = str(row0.get("image_name", ""))
                img_path = str(row0.get("image_path", ""))
                defect_item = str(row0.get("defect_item", ""))

        label = from_sampler(verdict, result, defect_item)

        base = {
            "order_no": order,
            "image_name": img_name,
            "image_path": img_path,
            "download_url": build_download_url(img_path, img_name) if (img_path and img_name) else "",
            "defect_item": defect_item,
            "labeler": labeler,
            "labeled_at": datetime.now().isoformat(timespec="seconds"),
        }

        if label == NEEDS_REVIEW:
            review.append({**base, "sampler_verdict": verdict, "sampler_result": result})
        else:
            labels.append({
                **base,
                "label": label,
                "urgency": urgency_of(label),
                "review_status": "AUTO" if label == Label.NORMAL.value else "PENDING",
            })

    # 저장
    jsonl = out_dir / "labels.jsonl"
    with open(jsonl, "w", encoding="utf-8") as f:
        for row in labels:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    review_csv = out_dir / "_needs_review.csv"
    if review:
        pd.DataFrame(review).to_csv(review_csv, index=False, encoding="utf-8-sig")

    print(f"확정 라벨: {len(labels)}건 → {jsonl}")
    print(f"세분 필요: {len(review)}건 → {review_csv if review else '(없음)'}")
    dist = pd.Series([l['label'] for l in labels]).value_counts().to_dict()
    print(f"클래스 분포: {dist}")


def _find(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("verdict_xlsx", help="점검결과확인서.xlsx 경로")
    ap.add_argument("--sap", default=None, help="원본 SAP 추출 xlsx (이미지/부적합항목 결합용)")
    ap.add_argument("--out", default="data/labels", help="출력 폴더")
    ap.add_argument("--labeler", default="unknown", help="라벨러 이름")
    args = ap.parse_args()
    convert(Path(args.verdict_xlsx), args.sap, Path(args.out), args.labeler)
