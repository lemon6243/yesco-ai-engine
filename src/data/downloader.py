"""사내 이미지 서버에서 이미지 다운로드"""
import requests
from pathlib import Path
from PIL import Image
import io
from typing import Optional

from src.utils.config import SAMPLES_DIR
from src.data.url_parser import parse_image_url, ImageMetadata


def download_image(
    url_or_filepath: str,
    save_dir: Path = SAMPLES_DIR,
    timeout: int = 10,
    save: bool = True,
) -> tuple[Image.Image, Optional[Path], ImageMetadata]:
    """
    사내 이미지 서버에서 이미지를 다운로드
    
    Args:
        url_or_filepath: HTML 뷰어 URL 또는 filepath 자체
        save_dir: 저장 경로
        timeout: 요청 타임아웃
        save: True면 디스크에 저장
    
    Returns:
        (PIL Image, 저장 경로, 메타데이터)
    """
    metadata = parse_image_url(url_or_filepath)
    
    print(f"⬇️  다운로드: {metadata.filename}")
    response = requests.get(metadata.direct_url, timeout=timeout)
    response.raise_for_status()
    
    # 이미지 확인
    content = response.content
    if content.startswith(b"<"):
        raise ValueError(
            "이미지가 아닌 HTML이 반환됨. "
            "direct_url이 올바른지 확인 필요."
        )
    
    img = Image.open(io.BytesIO(content))
    print(f"   ✅ {img.size[0]}x{img.size[1]} {img.format} ({len(content):,} bytes)")
    
    save_path = None
    if save:
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / metadata.filename
        img.save(save_path)
        print(f"   💾 {save_path}")
    
    return img, save_path, metadata


if __name__ == "__main__":
    # 테스트 1: HTML 뷰어 URL (원본 그대로 넣어도 OK)
    test_url = (
        "http://10.157.1.20:8020/pic/single.do?filepath="
        "J%3a%2fMOBILESMS%2fIMAGE%2f20260506%2fSAFE%2f01%2f"
        "202605%2f20260506%2f9007%2f"
        "SAFE_01_800064879056_20260506082103.jpg"
    )
    
    print("=" * 60)
    print("📸 이미지 다운로드 테스트")
    print("=" * 60)
    
    try:
        img, path, meta = download_image(test_url)
        print()
        print(meta)
        print()
        print(f"✅ 성공!")
    except Exception as e:
        print(f"\n❌ 오류: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
