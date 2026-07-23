"""
SAP 데이터에서 5건만 골라서 다운로드 테스트
- 실제 서버 응답 확인
- 다양한 연도(E:/, J:/) 드라이브 모두 동작하는지
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from PIL import Image
import io
from src.data.sap_loader import load_sap_excel
from src.utils.config import SAMPLES_DIR


def test_download(url: str, save_name: str) -> dict:
    """단일 URL 다운로드 테스트"""
    result = {
        "url": url,
        "save_name": save_name,
        "success": False,
        "size_bytes": 0,
        "dimensions": None,
        "error": None,
    }
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # HTML 응답이면 실패
        if response.content.startswith(b"<"):
            result["error"] = "HTML 응답 (이미지 아님)"
            return result
        
        # JPEG 시그니처 확인
        if not response.content.startswith(b"\xff\xd8"):
            result["error"] = f"JPEG 아님 (시작 바이트: {response.content[:4].hex()})"
            return result
        
        # PIL로 검증
        img = Image.open(io.BytesIO(response.content))
        
        result["success"] = True
        result["size_bytes"] = len(response.content)
        result["dimensions"] = f"{img.width}x{img.height}"
        
        # 저장
        save_path = SAMPLES_DIR / save_name
        with open(save_path, "wb") as f:
            f.write(response.content)
        
    except requests.Timeout:
        result["error"] = "타임아웃 (10초)"
    except requests.ConnectionError:
        result["error"] = "연결 실패"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    
    return result


def main():
    excel_path = Path("data/sap_exports/sample.xlsx")
    df = load_sap_excel(excel_path)
    
    # 연도별로 다양하게 5건 샘플링
    # 2019, 2021, 2023, 2025, 2026 같이 분산
    df["year"] = df["inspection_date"].str[:4]
    sample_df = df.groupby("year").head(1).head(5).reset_index(drop=True)
    
    print("=" * 70)
    print(f"🧪 다운로드 테스트: {len(sample_df)}건")
    print("=" * 70)
    
    success_count = 0
    fail_count = 0
    
    for idx, row in sample_df.iterrows():
        print(f"\n[{idx+1}/{len(sample_df)}] {row['inspection_date']} | {row['boiler_maker']} | 오더 {row['order_no']}")
        print(f"   URL: {row['download_url'][:100]}...")
        
        result = test_download(row["download_url"], row["image_name"])
        
        if result["success"]:
            print(f"   ✅ 성공: {result['size_bytes']:,} bytes, {result['dimensions']}")
            success_count += 1
        else:
            print(f"   ❌ 실패: {result['error']}")
            fail_count += 1
    
    print("\n" + "=" * 70)
    print(f"📊 결과: 성공 {success_count}건 / 실패 {fail_count}건")
    print("=" * 70)
    
    if success_count == len(sample_df):
        print("\n🎉 모든 이미지 다운로드 성공! 전체 126건 다운로드 가능합니다.")
    elif success_count > 0:
        print(f"\n⚠️  일부 실패. 실패 원인 분석 필요.")
    else:
        print(f"\n🚨 전부 실패. 서버 또는 URL 형식 점검 필요.")


if __name__ == "__main__":
    main()
