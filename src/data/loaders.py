"""SAP에서 받은 데이터를 표준 형식으로 변환"""
import pandas as pd
from pathlib import Path
from typing import Optional


# SAP 컬럼명 → 표준 컬럼명 매핑
# 실제 SAP 컬럼명에 맞춰 수정 필요
COLUMN_MAPPING = {
    # 가능한 SAP 컬럼명들 (대소문자/한글 모두)
    "이미지URL": "url",
    "사진주소": "url",
    "filepath": "url",
    "URL": "url",
    
    "점검결과": "inspection_result",
    "결과": "inspection_result",
    "판정": "inspection_result",
    
    "부적합유형": "defect_type",
    "결함종류": "defect_type",
    "불량유형": "defect_type",
    
    "시설구분": "facility_type",
    "설비종류": "facility_type",
    
    "오더번호": "order_no",
    "ORDER_NO": "order_no",
    
    "점검일": "inspection_date",
    "점검일자": "inspection_date",
}


def load_from_excel(
    filepath: Path | str,
    sheet_name: Optional[str] = None,
) -> list[dict]:
    """Excel에서 URL 리스트 로드"""
    df = pd.read_excel(filepath, sheet_name=sheet_name or 0)
    return _normalize(df)


def load_from_csv(filepath: Path | str, encoding: str = "utf-8") -> list[dict]:
    """CSV에서 URL 리스트 로드"""
    try:
        df = pd.read_csv(filepath, encoding=encoding)
    except UnicodeDecodeError:
        # 한글 CSV는 cp949일 가능성
        df = pd.read_csv(filepath, encoding="cp949")
    return _normalize(df)


def load_from_text(filepath: Path | str) -> list[dict]:
    """텍스트 파일 (한 줄에 하나의 URL)"""
    with open(filepath, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    return [{"url": url} for url in urls]


def _normalize(df: pd.DataFrame) -> list[dict]:
    """컬럼명 표준화 + dict 리스트로 변환"""
    # 컬럼명 표준화
    rename_map = {col: COLUMN_MAPPING[col] for col in df.columns if col in COLUMN_MAPPING}
    df = df.rename(columns=rename_map)
    
    # url 또는 filepath 컬럼 필수
    if "url" not in df.columns:
        raise ValueError(
            f"URL 컬럼을 찾을 수 없습니다. "
            f"사용 가능한 컬럼: {list(df.columns)}\n"
            f"COLUMN_MAPPING에 추가 필요"
        )
    
    return df.to_dict(orient="records")


if __name__ == "__main__":
    # 사용 예시 (실제 파일 받으면 테스트)
    print("📋 지원 형식:")
    print("  - Excel: load_from_excel('data/sap_export.xlsx')")
    print("  - CSV:   load_from_csv('data/sap_export.csv')")
    print("  - Text:  load_from_text('data/urls.txt')")
