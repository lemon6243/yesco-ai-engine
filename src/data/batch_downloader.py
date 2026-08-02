"""대량 이미지 다운로드 — URL 리스트로부터 일괄 다운로드"""
import time
import json
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.utils.config import SAMPLES_DIR, LABELS_DIR
from src.data.url_parser import parse_image_url, ImageMetadata


@dataclass
class DownloadResult:
    """다운로드 결과"""
    filename: str
    filepath: str
    direct_url: str
    success: bool
    save_path: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    # 메타데이터
    order_no: Optional[str] = None
    inspection_date: Optional[str] = None
    inspection_time: Optional[str] = None
    safe_type: Optional[str] = None
    # 추가 정보 (SAP에서 받은 것)
    inspection_result: Optional[str] = None  # 정상/부적합
    defect_type: Optional[str] = None        # 이탈/손상
    facility_type: Optional[str] = None      # 보일러/가스레인지
    # 추가 정보 (yesco-inspection-sampler 에서 받은 것 — 실사 검토 라벨)
    verdict: Optional[str] = None            # 정상/의심/부적합 (검토 뷰어 판정)
    result: Optional[str] = None             # 적합/확인요청/미판정
    comment: Optional[str] = None            # 검토자 코멘트
    meta_risk_score: Optional[float] = None  # 허위/부실점검 위험도(0~100)
    distance_diff_m: Optional[float] = None  # GPS 이격 거리(m)
    duration_min: Optional[float] = None     # 점검 소요 시간(분)
    labeler: Optional[str] = None            # 라벨링(검토)한 사람
    labeled_at: Optional[str] = None         # 라벨링(검토) 시각
    source: Optional[str] = None             # 라벨 출처 (예: yesco-inspection-sampler.ReviewViewer)
    defect_points_json: Optional[str] = None  # 클릭으로 표시한 문제부위 좌표 (JSON 문자열)


def download_one(
    url_or_filepath: str,
    save_dir: Path,
    extra_info: Optional[dict] = None,
    timeout: int = 15,
    skip_existing: bool = True,
) -> DownloadResult:
    """단일 이미지 다운로드 (에러 시에도 결과 반환)"""
    try:
        metadata = parse_image_url(url_or_filepath)
    except Exception as e:
        return DownloadResult(
            filename="unknown",
            filepath=url_or_filepath,
            direct_url="",
            success=False,
            error=f"URL 파싱 실패: {e}",
        )
    
    save_path = save_dir / metadata.filename
    
    # 이미 있으면 스킵
    if skip_existing and save_path.exists():
        return DownloadResult(
            filename=metadata.filename,
            filepath=metadata.filepath,
            direct_url=metadata.direct_url,
            success=True,
            save_path=str(save_path),
            file_size=save_path.stat().st_size,
            order_no=metadata.order_no,
            inspection_date=metadata.inspection_date,
            inspection_time=metadata.inspection_time,
            safe_type=metadata.safe_type,
            **(extra_info or {}),
        )
    
    try:
        response = requests.get(metadata.direct_url, timeout=timeout)
        response.raise_for_status()
        content = response.content
        
        if content.startswith(b"<"):
            return DownloadResult(
                filename=metadata.filename,
                filepath=metadata.filepath,
                direct_url=metadata.direct_url,
                success=False,
                error="HTML 응답 (이미지 아님)",
            )
        
        save_dir.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(content)
        
        return DownloadResult(
            filename=metadata.filename,
            filepath=metadata.filepath,
            direct_url=metadata.direct_url,
            success=True,
            save_path=str(save_path),
            file_size=len(content),
            order_no=metadata.order_no,
            inspection_date=metadata.inspection_date,
            inspection_time=metadata.inspection_time,
            safe_type=metadata.safe_type,
            **(extra_info or {}),
        )
    
    except requests.exceptions.Timeout:
        return DownloadResult(
            filename=metadata.filename,
            filepath=metadata.filepath,
            direct_url=metadata.direct_url,
            success=False,
            error="Timeout",
        )
    except Exception as e:
        return DownloadResult(
            filename=metadata.filename,
            filepath=metadata.filepath,
            direct_url=metadata.direct_url,
            success=False,
            error=f"{type(e).__name__}: {e}",
        )


def download_batch(
    items: list[dict],
    save_dir: Path = SAMPLES_DIR,
    max_workers: int = 5,
    skip_existing: bool = True,
    save_report: bool = True,
) -> list[DownloadResult]:
    """
    대량 다운로드 (멀티스레드)
    
    Args:
        items: [{"url": "...", "result": "부적합", "defect_type": "이탈", ...}, ...]
               최소 "url" 또는 "filepath" 키 필요
        save_dir: 저장 경로
        max_workers: 동시 다운로드 수 (서버 부하 고려)
        skip_existing: 기존 파일 스킵
        save_report: 다운로드 리포트 저장
    
    Returns:
        DownloadResult 리스트
    """
    print(f"📦 대량 다운로드 시작: {len(items)}개")
    print(f"   저장 위치: {save_dir}")
    print(f"   동시 처리: {max_workers}개")
    print()
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 작업 제출
        future_to_item = {}
        for item in items:
            url = item.get("url") or item.get("filepath")
            if not url:
                continue
            
            extra_info = {
                k: v for k, v in item.items()
                if k not in ("url", "filepath") and v is not None
            }
            # defect_points 는 list[dict] 형태라 dataclass 필드(str)에 맞게 JSON 문자열로 변환
            if "defect_points" in extra_info and "defect_points_json" not in extra_info:
                extra_info["defect_points_json"] = json.dumps(
                    extra_info.pop("defect_points"), ensure_ascii=False
                )
            else:
                extra_info.pop("defect_points", None)

            # 인정된 필드만 필터링 (SAP 유래 필드 + yesco-inspection-sampler 유래 라벨 필드)
            allowed_keys = {
                "inspection_result", "defect_type", "facility_type",
                "verdict", "result", "comment", "meta_risk_score",
                "distance_diff_m", "duration_min", "labeler", "labeled_at",
                "source", "defect_points_json",
            }
            extra_info = {k: v for k, v in extra_info.items() if k in allowed_keys}
            
            future = executor.submit(
                download_one, url, save_dir, extra_info, 15, skip_existing
            )
            future_to_item[future] = item
        
        # 진행률 표시
        with tqdm(total=len(future_to_item), desc="다운로드") as pbar:
            for future in as_completed(future_to_item):
                result = future.result()
                results.append(result)
                
                # 진행 정보
                if result.success:
                    pbar.set_postfix_str(f"✓ {result.filename[:40]}")
                else:
                    pbar.set_postfix_str(f"✗ {result.error[:40]}")
                pbar.update(1)
    
    # 통계
    success = sum(1 for r in results if r.success)
    failed = len(results) - success
    total_size_mb = sum(r.file_size or 0 for r in results) / (1024 * 1024)
    
    print()
    print("=" * 60)
    print(f"📊 다운로드 완료")
    print(f"   ✅ 성공: {success}개")
    print(f"   ❌ 실패: {failed}개")
    print(f"   💾 총 용량: {total_size_mb:.1f} MB")
    print("=" * 60)
    
    # 리포트 저장
    if save_report:
        report_path = LABELS_DIR / "download_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(
                [asdict(r) for r in results],
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"📋 리포트 저장: {report_path}")
    
    # 실패한 것 출력
    if failed > 0:
        print(f"\n❌ 실패 목록:")
        for r in results:
            if not r.success:
                print(f"   - {r.filename}: {r.error}")
    
    return results


if __name__ == "__main__":
    # 테스트: 같은 이미지 3개 (실제 사용시엔 SAP에서 받은 리스트)
    test_items = [
        {
            "url": (
                "http://10.157.1.20:8020/pic/single.do?filepath="
                "J%3a%2fMOBILESMS%2fIMAGE%2f20260506%2fSAFE%2f01%2f"
                "202605%2f20260506%2f9007%2f"
                "SAFE_01_800064879056_20260506082103.jpg"
            ),
            "inspection_result": "부적합",
            "defect_type": "이탈",
            "facility_type": "보일러",
        },
    ]
    
    results = download_batch(test_items, max_workers=2)
    
    print("\n첫 결과:")
    print(json.dumps(asdict(results[0]), indent=2, ensure_ascii=False))
