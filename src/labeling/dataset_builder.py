"""
yesco-inspection-sampler 연동 — 데이터셋 빌더

[흐름]
1. yesco-inspection-sampler 의 ReviewViewer."🤖 AI 라벨 내보내기" 로 만든 JSON 파일을 읽는다.
   (스키마: order_no, center_code, center_name, inspector, inspection_date,
             image_path, image_name, download_url, defect_item,
             verdict(정상/의심/부적합), result, comment,
             defect_points([{panel,x_frac,y_frac}, ...]),
             meta_risk_score, distance_diff_m, duration_min,
             labeler, labeled_at, source)
2. verdict + defect_item(+comment) 을 5-클래스 라벨(NORMAL/DAMAGED_SILICONE/
   DAMAGED_PIPE/DETACHED_PARTIAL/DETACHED_FULL/UNCLEAR)로 매핑한다.
   (src/labeling/label_mapping.py)
3. (옵션) 이미지를 실제로 다운로드한다 (src/data/batch_downloader.py 재사용).
4. 학습에 바로 쓸 수 있는 data/labels/dataset.csv 를 만든다.
   → 컬럼: image_path, image_name, order_no, label, urgency, confidence,
            needs_review, defect_location, defect_points, notes,
            meta_risk_score, distance_diff_m, duration_min,
            labeler, labeled_at, source, review_status
   (docs/guides/labeling_guide_v0.1.md 의 라벨링 데이터 구조와 최대한 필드를 맞췄다)
5. 라벨 매핑이 애매했던(needs_review=True) 건은 data/labels/unmapped_defect_items.csv
   로 따로 뽑아준다 → defect_item 실제 값 확인 후 label_mapping.py 의
   KEYWORD_RULES 를 보강하는 데 사용.

CLI 사용 예:
    python -m src.labeling.dataset_builder path/to/ai_labels.json
    python -m src.labeling.dataset_builder path/to/ai_labels.json --download
"""
import argparse
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils.config import LABELS_DIR, SAMPLES_DIR
from src.labeling.label_mapping import map_verdict_to_label
from src.data.batch_downloader import download_batch

DATASET_CSV_PATH = LABELS_DIR / "dataset.csv"
UNMAPPED_CSV_PATH = LABELS_DIR / "unmapped_defect_items.csv"


def load_sampler_export(json_path: Path | str) -> list[dict]:
    """sampler 가 내보낸 AI 라벨 JSON(리스트 또는 단일 dict)을 읽는다."""
    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    return data


def _defect_location_from_points(defect_points: Optional[list[dict]]) -> str:
    """클릭 좌표(x_frac, y_frac)를 라벨링 가이드의 defect_location 대분류
    (TOP_JOINT/BOTTOM_JOINT/CENTER 등)로 대략 변환.
    좌표가 여러 개면 첫 번째 좌표 기준. 좌표가 없으면 빈 문자열.
    """
    if not defect_points:
        return ""
    pt = defect_points[0]
    y = pt.get("y_frac")
    if y is None:
        return ""
    if y < 0.4:
        return "TOP_JOINT"
    if y > 0.6:
        return "BOTTOM_JOINT"
    return "CENTER"


def build_dataset(
    records: list[dict],
    review_status: str = "PENDING",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    sampler export 레코드 리스트 → (dataset_df, unmapped_df)

    dataset_df: 학습/검수에 쓸 전체 라벨 데이터셋
    unmapped_df: needs_review=True 인 건만 모은 서브셋 (defect_item 규칙 보강용)
    """
    rows = []
    for rec in records:
        verdict = rec.get("verdict")
        defect_item = rec.get("defect_item")
        comment = rec.get("comment")
        defect_points = rec.get("defect_points") or []

        mapped = map_verdict_to_label(
            verdict=verdict,
            defect_item=defect_item,
            comment=comment,
            has_defect_points=bool(defect_points),
        )

        rows.append({
            "order_no": rec.get("order_no"),
            "center_code": rec.get("center_code"),
            "center_name": rec.get("center_name"),
            "image_path": rec.get("image_path"),
            "image_name": rec.get("image_name"),
            "download_url": rec.get("download_url"),
            "label": mapped.label,
            "urgency": mapped.urgency,
            "confidence": mapped.confidence,
            "needs_review": mapped.needs_review,
            "map_reason": mapped.reason,
            "defect_item_raw": defect_item,
            "defect_location": _defect_location_from_points(defect_points),
            "defect_points": json.dumps(defect_points, ensure_ascii=False),
            "notes": comment or "",
            "verdict_raw": verdict,
            "result_raw": rec.get("result"),
            "meta_risk_score": rec.get("meta_risk_score"),
            "distance_diff_m": rec.get("distance_diff_m"),
            "duration_min": rec.get("duration_min"),
            "labeler": rec.get("labeler"),
            "labeled_at": rec.get("labeled_at"),
            "source": rec.get("source", "yesco-inspection-sampler.ReviewViewer"),
            "review_status": review_status,
        })

    dataset_df = pd.DataFrame(rows)
    unmapped_df = dataset_df[dataset_df["needs_review"] == True].copy() if len(dataset_df) else dataset_df

    return dataset_df, unmapped_df


def append_to_dataset_csv(new_df: pd.DataFrame, csv_path: Path = DATASET_CSV_PATH) -> pd.DataFrame:
    """기존 dataset.csv 가 있으면 order_no 기준으로 중복 제거하며 합친다."""
    if csv_path.exists():
        old_df = pd.read_csv(csv_path, dtype=str)
        combined = pd.concat([old_df, new_df.astype(str)], ignore_index=True)
        if "order_no" in combined.columns:
            combined = combined.drop_duplicates(subset=["order_no", "image_name"], keep="last")
    else:
        combined = new_df
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return combined


def maybe_download_images(dataset_df: pd.DataFrame, save_dir: Path = SAMPLES_DIR):
    """dataset_df 의 download_url 을 이용해 실제 이미지를 다운로드 (batch_downloader 재사용)."""
    items = []
    for _, row in dataset_df.iterrows():
        url = row.get("download_url")
        if not url or str(url).lower() == "nan":
            continue
        items.append({
            "url": url,
            "inspection_result": row.get("result_raw"),
            "defect_type": row.get("label"),
            "verdict": row.get("verdict_raw"),
            "result": row.get("result_raw"),
            "comment": row.get("notes"),
            "meta_risk_score": row.get("meta_risk_score"),
            "distance_diff_m": row.get("distance_diff_m"),
            "duration_min": row.get("duration_min"),
            "labeler": row.get("labeler"),
            "labeled_at": row.get("labeled_at"),
            "source": row.get("source"),
        })
    if not items:
        print("⚠️  다운로드할 이미지가 없습니다 (download_url 없음).")
        return []
    return download_batch(items, save_dir=save_dir)


def main():
    parser = argparse.ArgumentParser(
        description="yesco-inspection-sampler 에서 내보낸 AI 라벨 JSON을 학습용 dataset.csv로 변환"
    )
    parser.add_argument("json_path", help="ReviewViewer.export_ai_labels() 로 만든 JSON 파일 경로")
    parser.add_argument("--download", action="store_true", help="이미지도 함께 다운로드")
    parser.add_argument(
        "--review-status", default="PENDING",
        help="review_status 컬럼에 채울 기본값 (기본: PENDING)"
    )
    args = parser.parse_args()

    records = load_sampler_export(args.json_path)
    print(f"📥 sampler 라벨 {len(records)}건 로드: {args.json_path}")

    dataset_df, unmapped_df = build_dataset(records, review_status=args.review_status)

    combined = append_to_dataset_csv(dataset_df)
    print(f"💾 dataset.csv 저장: {DATASET_CSV_PATH} (누적 {len(combined)}건)")

    if len(unmapped_df):
        UNMAPPED_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        unmapped_df.to_csv(UNMAPPED_CSV_PATH, index=False, encoding="utf-8-sig")
        print(
            f"⚠️  라벨 자동매핑 불확실 {len(unmapped_df)}건 → {UNMAPPED_CSV_PATH}\n"
            f"   (defect_item 실제 값을 확인해 src/labeling/label_mapping.py 의 "
            f"KEYWORD_RULES 를 보강해주세요)"
        )

    # 라벨 분포 요약
    if len(dataset_df):
        print("\n📊 라벨 분포:")
        print(dataset_df["label"].value_counts().to_string())

    if args.download:
        print("\n📦 이미지 다운로드 시작...")
        maybe_download_images(dataset_df)


if __name__ == "__main__":
    main()
