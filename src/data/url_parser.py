"""
사내 이미지 URL 파싱 및 생성

[URL 종류]

1. HTML 뷰어 (브라우저용):
   http://10.157.1.20:8020/pic/single.do?filepath=...

2. ⭐ 실제 이미지 직접 다운로드:
   http://10.157.1.20:8020/image?filepath=J:/MOBILESMS/IMAGE/.../xxx.jpg
"""
import re
from urllib.parse import quote, unquote
from dataclasses import dataclass
from typing import Optional

from src.utils.config import IMAGE_DIRECT_URL


@dataclass
class ImageMetadata:
    """이미지 URL/경로에서 추출한 메타데이터"""
    filepath: str                          # J:/MOBILESMS/IMAGE/.../xxx.jpg
    filename: str                          # SAFE_01_xxx.jpg
    direct_url: str                        # 다운로드용 URL
    order_no: Optional[str] = None         # 800064879056 (오더번호)
    inspection_date: Optional[str] = None  # 20260506
    inspection_time: Optional[str] = None  # 082103
    safe_type: Optional[str] = None        # SAFE_01
    
    def __str__(self):
        return (
            f"📷 {self.filename}\n"
            f"   📅 점검일: {self.inspection_date} {self.inspection_time}\n"
            f"   🔢 오더번호: {self.order_no}\n"
            f"   🏷️  타입: {self.safe_type}"
        )


def parse_filename(filename: str) -> dict:
    """파일명에서 정보 추출
    예: SAFE_01_800064879056_20260506082103.jpg
    """
    match = re.match(
        r"(?P<type1>[A-Z]+)_(?P<type2>\d+)_(?P<order>\d+)_(?P<dt>\d{14})\.\w+",
        filename
    )
    if not match:
        return {}
    
    d = match.groupdict()
    return {
        "safe_type": f"{d['type1']}_{d['type2']}",
        "order_no": d["order"],
        "inspection_date": d["dt"][:8],
        "inspection_time": d["dt"][8:],
    }


def parse_image_url(url: str) -> ImageMetadata:
    """URL(또는 filepath)에서 메타데이터 추출"""
    # filepath 파라미터 추출
    match = re.search(r"filepath=([^&]+)", url)
    if not match:
        # URL이 아니라 filepath 자체가 들어왔을 수도
        if "/" in url or "\\" in url:
            filepath = url.replace("\\", "/")
        else:
            raise ValueError(f"filepath를 찾을 수 없음: {url}")
    else:
        filepath = unquote(match.group(1)).replace("\\", "/")
    
    filename = filepath.split("/")[-1]
    direct_url = build_direct_image_url(filepath)
    
    metadata = ImageMetadata(
        filepath=filepath,
        filename=filename,
        direct_url=direct_url,
    )
    
    # 파일명에서 정보 추출
    info = parse_filename(filename)
    for key, value in info.items():
        setattr(metadata, key, value)
    
    return metadata


def build_direct_image_url(filepath: str) -> str:
    """파일 경로 → 실제 이미지 다운로드 URL
    
    참고: 사내 서버는 filepath를 URL 인코딩 없이도 받지만,
          안전을 위해 콜론(:)만 인코딩하고 슬래시(/)는 유지.
    """
    # J:/MOBILESMS → J%3A/MOBILESMS (콜론만 인코딩)
    encoded = filepath.replace(":", "%3A")
    return f"{IMAGE_DIRECT_URL}?filepath={encoded}"


if __name__ == "__main__":
    test_cases = [
        # HTML 뷰어 URL
        "http://10.157.1.20:8020/pic/single.do?filepath="
        "J%3a%2fMOBILESMS%2fIMAGE%2f20260506%2fSAFE%2f01%2f"
        "202605%2f20260506%2f9007%2f"
        "SAFE_01_800064879056_20260506082103.jpg",
        
        # filepath만
        "J:/MOBILESMS/IMAGE/20260506/SAFE/01/202605/20260506/9007/"
        "SAFE_01_800064879056_20260506082103.jpg",
    ]
    
    for i, url in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"테스트 {i}")
        print(f"{'=' * 60}")
        meta = parse_image_url(url)
        print(meta)
        print(f"\n다운로드용 URL:\n{meta.direct_url}")
