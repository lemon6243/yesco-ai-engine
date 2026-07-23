"""
SAP 추출 Excel/CSV 파일 로더
- 21개 컬럼 표준화
- 이미지 다운로드 URL 자동 생성
- GPS 거리 검증
"""
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.config import IMAGE_DIRECT_URL


# SAP 원본 컬럼 → 표준 컬럼 매핑
SAP_COLUMN_MAPPING = {
    "이미지경로": "image_path",
    "이미지이름": "image_name",
    "작업장": "workplace",
    "오더": "order_no",
    "설비": "equipment_no",
    "주소": "address",
    "사원": "inspector",
    "검사일": "inspection_date",
    "시작시간": "start_time",
    "종료시간": "end_time",
    "*보일러제작사": "boiler_maker",
    "*보일러용량": "boiler_capacity",
    "*보일러설치장소": "install_location",
    "*보일러배기방식": "exhaust_type",
    "*보일러설치일": "install_date",
    "GPS위치 경도": "gps_lon",
    "GPS위치 위도": "gps_lat",
    "주소좌표 경도": "addr_lon",
    "주소좌표 위도": "addr_lat",
    "거리차이(M)": "distance_diff_m",
    "요금유형": "fee_type",
}


@dataclass
class InspectionRecord:
    """점검 한 건 (이미지 1장)"""
    order_no: str
    image_name: str
    image_path: str
    download_url: str          # 우리가 만든 다운로드 URL
    inspector: str
    inspection_date: str
    address: str
    boiler_maker: str
    boiler_capacity: str
    install_location: str
    exhaust_type: str
    distance_diff_m: Optional[float]
    gps_valid: bool            # 거리차이 50m 이내면 True


def build_download_url(image_path: str, image_name: str) -> str:
    """
    image_path: 'E:/MOBILESMS/IMAGE/20191031/SAFE/01/201910/20191031/9001/'
    image_name: 'SAFE_01_800041984577_20191031080225.jpg'
    → http://10.157.1.20:8020/image?filepath=E%3A/MOBILESMS/.../9001/SAFE_01_....jpg
    """
    # 경로 끝에 슬래시가 없으면 추가
    if not image_path.endswith("/"):
        image_path += "/"
    
    full_path = image_path + image_name
    # 콜론만 인코딩 (서버가 /를 그대로 받음)
    encoded = full_path.replace(":", "%3A")
    return f"{IMAGE_DIRECT_URL}?filepath={encoded}"


def load_sap_excel(file_path: str | Path) -> pd.DataFrame:
    """
    SAP 추출 Excel을 로드하고 표준 컬럼명으로 변환
    """
    file_path = Path(file_path)
    
    # 오더번호 과학적표기법 방지: 모든 컬럼을 문자열로
    if file_path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path, dtype=str)
    else:
        df = pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
    
    # 컬럼명 표준화
    df = df.rename(columns=SAP_COLUMN_MAPPING)
    
    # 다운로드 URL 생성
    df["download_url"] = df.apply(
        lambda r: build_download_url(r["image_path"], r["image_name"]),
        axis=1
    )
    
    # 거리차이 숫자 변환
    df["distance_diff_m"] = pd.to_numeric(df["distance_diff_m"], errors="coerce")
    df["gps_valid"] = df["distance_diff_m"].fillna(999) <= 50
    
    return df


def summary(df: pd.DataFrame) -> dict:
    """데이터 요약 통계"""
    return {
        "총 건수": len(df),
        "고유 오더 수": df["order_no"].nunique(),
        "고유 점검원 수": df["inspector"].nunique(),
        "점검일 범위": f"{df['inspection_date'].min()} ~ {df['inspection_date'].max()}",
        "보일러 제작사 TOP5": df["boiler_maker"].value_counts().head().to_dict(),
        "배기방식 분포": df["exhaust_type"].value_counts().to_dict(),
        "설치장소 분포": df["install_location"].value_counts().to_dict(),
        "GPS 정상(50m 이내)": int(df["gps_valid"].sum()),
        "GPS 이상(50m 초과)": int((~df["gps_valid"]).sum()),
    }


if __name__ == "__main__":
    import json
    
    # 테스트: data/sap_exports/ 폴더에 Excel 파일이 있다고 가정
    test_file = Path("data/sap_exports/sample.xlsx")
    
    if not test_file.exists():
        print(f"❌ 테스트 파일이 없습니다: {test_file}")
        print("   data/sap_exports/ 폴더에 SAP 추출 Excel을 넣어주세요.")
        sys.exit(1)
    
    print("=" * 60)
    print(f"📊 SAP 데이터 로드: {test_file.name}")
    print("=" * 60)
    
    df = load_sap_excel(test_file)
    print(f"\n✅ 로드 완료: {len(df):,}건\n")
    
    print("📋 상위 3건:")
    print(df[["order_no", "inspector", "inspection_date", 
              "boiler_maker", "distance_diff_m"]].head(3).to_string())
    
    print("\n📊 요약 통계:")
    stats = summary(df)
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
    
    print("\n🔗 첫 번째 다운로드 URL:")
    print(df.iloc[0]["download_url"])
