"""프로젝트 전역 설정"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
LABELS_DIR = DATA_DIR / "labels"
CACHE_DIR = DATA_DIR / "cache"

# 사내 이미지 서버
IMAGE_SERVER_BASE = os.getenv("IMAGE_SERVER_BASE", "http://10.157.1.20:8020")

# URL 엔드포인트
VIEWER_URL_SINGLE = f"{IMAGE_SERVER_BASE}/pic/single.do"  # HTML 뷰어 (브라우저용)
VIEWER_URL_BULK = f"{IMAGE_SERVER_BASE}/pic/file.do"      # HTML 다건 뷰어
IMAGE_DIRECT_URL = f"{IMAGE_SERVER_BASE}/image"           # ⭐ 실제 이미지 직접 다운로드

# 폴더 자동 생성
for d in [SAMPLES_DIR, LABELS_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print(f"📁 PROJECT_ROOT:     {PROJECT_ROOT}")
    print(f"🌐 SERVER:           {IMAGE_SERVER_BASE}")
    print(f"🖼️  IMAGE_DIRECT_URL: {IMAGE_DIRECT_URL}")
