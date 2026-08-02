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
- [x] yesco-inspection-sampler(실사 검토 GUI) 연동 — 라벨 데이터 수집 파이프라인 구축
- [ ] 데이터 인벤토리 작성
- [ ] 라벨링 가이드라인 v1.0
- [ ] 시드 데이터 500장 구축
- [ ] 베이스라인 모델 학습

## 🔗 yesco-inspection-sampler 연동 (실사 검토 → AI 라벨)

팀에서 쓰는 실사 사진 검토 GUI([yesco-inspection-sampler](https://github.com/lemon6243/yesco-inspection-sampler))의
`ReviewViewer`에 아래 기능이 추가되어, 검토자가 사진을 보며 판정(정상/의심/부적합)하고
문제 부위를 클릭으로 표시하면 그 결과를 이 저장소의 학습 데이터로 바로 이어받을 수 있다.

- 실사 검토 시 GPS 이격거리·소요시간·사진 품질(흐림/노출)·사진 재사용(perceptual hash) 기반
  **허위/부실점검 위험도 스코어**를 자동 계산해 표시 (규칙 기반, 모델 불필요)
- 검토자가 '의심'/'부적합' 판정 시 사진 위 문제 부위를 클릭으로 표시 가능
- "🤖 AI 라벨 내보내기" 버튼으로 판정+좌표+위험도를 JSON으로 export

### 이 저장소에서 JSON을 학습 데이터셋으로 변환하기

```bash
# sampler 에서 내보낸 JSON → data/labels/dataset.csv 생성
python -m src.labeling.dataset_builder path/to/ai_labels.json

# 이미지까지 함께 다운로드하려면
python -m src.labeling.dataset_builder path/to/ai_labels.json --download
```

- `verdict`(정상/의심/부적합) + `defect_item`(자유 텍스트) → 5-클래스 라벨
  (`NORMAL`/`DAMAGED_SILICONE`/`DAMAGED_PIPE`/`DETACHED_PARTIAL`/`DETACHED_FULL`/`UNCLEAR`)
  매핑 규칙은 `src/labeling/label_mapping.py` 참고.
- 자동 매핑이 불확실한 건은 `data/labels/unmapped_defect_items.csv` 로 따로 뽑혀
  `needs_review=True` 로 표시됨 → 실제 `defect_item` 값 확인 후
  `label_mapping.py`의 `KEYWORD_RULES`를 보강하면 됨 (아직 실제 값 예시 미확보).
