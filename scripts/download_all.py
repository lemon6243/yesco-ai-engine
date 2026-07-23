"""
SAP 데이터의 모든 이미지를 멀티스레드로 다운로드
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import json
import time

from src.data.sap_loader import load_sap_excel

# 다운로드 저장 폴더
DOWNLOAD_DIR = Path("data/cache/images")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PATH = Path("data/cache/download_report.json")


def download_one(row_dict: dict) -> dict:
    """이미지 1장 다운로드"""
    url = row_dict["download_url"]
    filename = row_dict["image_name"]
    save_path = DOWNLOAD_DIR / filename
    
    result = {
        "order_no": row_dict["order_no"],
        "filename": filename,
        "success": False,
        "size_bytes": 0,
        "error": None,
    }
    
    # 이미 있으면 스킵
    if save_path.exists():
        result["success"] = True
        result["size_bytes"] = save_path.stat().st_size
        result["error"] = "skipped (already exists)"
        return result
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        if response.content.startswith(b"<"):
            result["error"] = "HTML 응답"
            return result
        
        if not response.content.startswith(b"\xff\xd8"):
            result["error"] = "JPEG 아님"
            return result
        
        with open(save_path, "wb") as f:
            f.write(response.content)
        
        result["success"] = True
        result["size_bytes"] = len(response.content)
        
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    
    return result


def main():
    # 1) SAP 데이터 로드
    df = load_sap_excel("data/sap_exports/sample.xlsx")
    print(f"📊 다운로드 대상: {len(df):,}건")
    
    rows = df.to_dict("records")
    
    # 2) 멀티스레드 다운로드 (서버 부하 고려해서 5개 동시)
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(download_one, row): row for row in rows}
        
        with tqdm(total=len(rows), desc="다운로드", unit="장") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                pbar.update(1)
                if not result["success"]:
                    pbar.write(f"❌ {result['filename']}: {result['error']}")
    
    elapsed = time.time() - start_time
    
    # 3) 통계
    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    skipped = [r for r in success if r.get("error") == "skipped (already exists)"]
    new_downloads = [r for r in success if r.get("error") != "skipped (already exists)"]
    
    total_size_mb = sum(r["size_bytes"] for r in success) / (1024 * 1024)
    
    print("\n" + "=" * 60)
    print("📊 다운로드 결과")
    print("=" * 60)
    print(f"  ✅ 성공:        {len(success):>4}건")
    print(f"     └ 신규:      {len(new_downloads):>4}건")
    print(f"     └ 스킵(기존): {len(skipped):>4}건")
    print(f"  ❌ 실패:        {len(failed):>4}건")
    print(f"  💾 총 용량:     {total_size_mb:,.1f} MB")
    print(f"  ⏱️  소요 시간:   {elapsed:.1f}초")
    print(f"  📁 저장 위치:   {DOWNLOAD_DIR}")
    
    # 4) 리포트 저장
    REPORT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  📄 리포트:      {REPORT_PATH}")
    
    if failed:
        print(f"\n⚠️  실패 목록:")
        for r in failed[:10]:
            print(f"   - {r['filename']}: {r['error']}")


if __name__ == "__main__":
    main()
