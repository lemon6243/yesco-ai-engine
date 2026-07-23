"""실제 이미지 엔드포인트 테스트"""
import requests
from pathlib import Path

# 진짜 이미지 URL (HTML 안의 JS에서 발견)
REAL_IMAGE_URL = (
    "http://10.157.1.20:8020/image?filepath="
    "J:/MOBILESMS/IMAGE/20260506/SAFE/01/202605/20260506/9007/"
    "SAFE_01_800064879056_20260506082103.jpg"
)


def test_real_url(url: str):
    print("=" * 70)
    print(f"🎯 실제 이미지 URL 테스트")
    print(f"   {url}")
    print("=" * 70)
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"\n📡 응답")
        print(f"   - Status: {response.status_code}")
        print(f"   - Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   - 크기: {len(response.content):,} bytes")
        
        # 시그니처 확인
        content = response.content
        if content.startswith(b"\xff\xd8\xff"):
            print(f"   - ✅ JPEG 이미지 확인!")
        elif content.startswith(b"\x89PNG"):
            print(f"   - ✅ PNG 이미지 확인!")
        elif content.startswith(b"<"):
            print(f"   - ❌ 또 HTML... 다른 방법 필요")
            print(f"   - 응답 처음 200자: {content[:200].decode('utf-8', errors='replace')}")
            return
        
        # 저장
        save_dir = Path("data/cache")
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / "real_test.jpg"
        with open(save_path, "wb") as f:
            f.write(content)
        print(f"\n💾 저장: {save_path}")
        
        # PIL로 열어보기
        from PIL import Image
        img = Image.open(save_path)
        print(f"\n🖼️  이미지 정보")
        print(f"   - 크기: {img.size[0]} x {img.size[1]}")
        print(f"   - 형식: {img.format}")
        print(f"   - 모드: {img.mode}")
        print(f"\n✅✅✅ 성공! 이제 다운로드 가능합니다 ✅✅✅")
        
    except Exception as e:
        print(f"\n❌ 오류: {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_real_url(REAL_IMAGE_URL)
