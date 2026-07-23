# YESCO AI 안전점검 엔진

가스시설(보일러/가스레인지) 연통 안전점검 AI 자동화 프로젝트

## 🎯 목표
- 현장 점검 사진에서 연통 결합부의 **이탈/손상** 자동 감지
- 100만+ 장의 누적 사진 데이터 활용
- 점진적 모델 고도화 (Pseudo-Labeling + Active Learning)

## 🏷️ 클래스 정의

| 클래스 | 정의 | 심각도 |
|--------|------|--------|
| **정상 (normal)** | 결합부 견고, 실리콘 양호, 연통 변형 없음 | ✅ 안전 |
| **손상 (damaged)** | 결합 유지되지만 실리콘 손상 또는 연통 변형 → CO 누출 가능 | ⚠️ 주의 |
| **이탈 (detached)** | 결합부 분리 → 즉시 CO 누출 위험, 중독사고 가능 | 🚨 위험 |

## 🛠️ 개발 환경

- Python 3.11
- VS Code
- Windows VDI 환경
- 학습용 GPU: Google Colab (무료)

## 📂 프로젝트 구조

\`\`\`
yesco-ai-engine/
├─ src/              # 핵심 코드
│  ├─ data/         # 데이터 다운로드/파싱
│  ├─ labeling/     # 라벨링 도구
│  └─ utils/        # 유틸리티
├─ notebooks/        # Jupyter 탐색
├─ docs/             # 문서
├─ data/             # 데이터 (gitignore)
└─ models/           # 모델 (gitignore)
\`\`\`

## 🚀 시작하기

\`\`\`bash
# 가상환경
py -3.11 -m venv venv
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 이미지 다운로드 테스트
python -m src.data.downloader
\`\`\`

## 📈 진행 현황

- [x] 프로젝트 구조 설계
- [x] 사내 이미지 서버 연동
- [ ] 데이터 인벤토리 작성
- [ ] 라벨링 가이드라인 v1.0
- [ ] 시드 데이터 500장 구축
- [ ] 베이스라인 모델 학습
