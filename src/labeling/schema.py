# 저장 위치: yesco-ai-engine/src/labeling/schema.py
"""
라벨 스키마 단일 소스 (Single Source of Truth)

- AI 학습에 쓰는 정식 클래스는 아래 LABELS 5종 + 보조 2종(UNCLEAR/EXCLUDED).
- 라벨링 가이드 v0.2 기준.
- sampler(점검결과확인서)의 판정값·결과값을 이 스키마로 매핑하는 규칙도 여기 둔다.
"""
from dataclasses import dataclass
from enum import Enum


class Label(str, Enum):
    NORMAL = "NORMAL"                     # 정상
    DAMAGED_SILICONE = "DAMAGED_SILICONE" # 실리콘 손상
    DAMAGED_PIPE = "DAMAGED_PIPE"         # 연통 손상
    DETACHED_PARTIAL = "DETACHED_PARTIAL" # 부분 이탈
    DETACHED_FULL = "DETACHED_FULL"       # 완전 이탈
    UNCLEAR = "UNCLEAR"                   # 판정 불가(학습 보류)
    EXCLUDED = "EXCLUDED"                 # 학습 제외


class Urgency(str, Enum):
    NONE = "NONE"
    SCHEDULED = "SCHEDULED"
    URGENT = "URGENT"
    IMMEDIATE = "IMMEDIATE"


@dataclass(frozen=True)
class LabelSpec:
    label: Label
    ko: str
    urgency: Urgency
    repair_window: str
    # 3클래스(coarse) 축소 매핑 — README/구모델 호환용
    coarse: str  # normal / damaged / detached


# 정식 5클래스 정의
LABEL_SPECS = {
    Label.NORMAL:          LabelSpec(Label.NORMAL,          "정상",      Urgency.NONE,      "정기 점검", "normal"),
    Label.DAMAGED_SILICONE:LabelSpec(Label.DAMAGED_SILICONE,"실리콘 손상", Urgency.SCHEDULED, "1-3개월",  "damaged"),
    Label.DAMAGED_PIPE:    LabelSpec(Label.DAMAGED_PIPE,    "연통 손상",  Urgency.URGENT,    "1주 이내", "damaged"),
    Label.DETACHED_PARTIAL:LabelSpec(Label.DETACHED_PARTIAL,"부분 이탈",  Urgency.URGENT,    "48시간",   "detached"),
    Label.DETACHED_FULL:   LabelSpec(Label.DETACHED_FULL,   "완전 이탈",  Urgency.IMMEDIATE, "즉시",     "detached"),
}

# 학습에 사용하는 클래스만 (UNCLEAR/EXCLUDED 제외)
TRAINABLE_LABELS = [
    Label.NORMAL, Label.DAMAGED_SILICONE, Label.DAMAGED_PIPE,
    Label.DETACHED_PARTIAL, Label.DETACHED_FULL,
]

# 클래스 인덱스 (모델 출력 순서 고정 — 절대 순서 바꾸지 말 것)
LABEL_TO_INDEX = {lab.value: i for i, lab in enumerate(TRAINABLE_LABELS)}
INDEX_TO_LABEL = {i: lab.value for lab, i in zip(TRAINABLE_LABELS, range(len(TRAINABLE_LABELS)))}


def urgency_of(label: str) -> str:
    """라벨 → 긴급도 문자열."""
    try:
        return LABEL_SPECS[Label(label)].urgency.value
    except (KeyError, ValueError):
        return Urgency.NONE.value


def to_coarse(label: str) -> str:
    """5클래스 → 3클래스(normal/damaged/detached). 미분류는 unclear."""
    try:
        return LABEL_SPECS[Label(label)].coarse
    except (KeyError, ValueError):
        return "unclear"


# ---------------------------------------------------------------------------
# sampler(점검결과확인서) 값 → 5클래스 매핑
# ---------------------------------------------------------------------------
# sampler 뷰어의 사람 판정은 정상/의심/부적합, 최종 결과는 적합/확인요청/미판정.
# 이 값들은 "손상 vs 이탈", "부분 vs 완전"을 구분하지 못하므로 자동 확정 불가.
# 따라서 아래 규칙은 '기계적으로 확정 가능한 것만' 확정하고,
# 나머지는 NEEDS_REVIEW로 남겨 사람이 세분 라벨을 마저 찍게 한다.

NEEDS_REVIEW = "__NEEDS_REVIEW__"


def from_sampler(verdict: str, result: str, defect_item: str = "") -> str:
    """
    sampler 판정/결과/부적합항목 → 5클래스(가능하면) 또는 NEEDS_REVIEW.

    verdict: 정상 / 의심 / 부적합 / 미판정
    result:  적합 / 확인요청 / 미판정
    defect_item: 부적합항목 텍스트(있으면 세분 힌트로 사용)
    """
    verdict = (verdict or "").strip()
    result = (result or "").strip()
    item = (defect_item or "").strip()

    # 정상/적합 → NORMAL 확정
    if verdict == "정상" or result == "적합":
        return Label.NORMAL.value

    # 미판정은 학습 보류
    if verdict == "미판정" or result == "미판정" or (not verdict and not result):
        return Label.UNCLEAR.value

    # 부적합/의심 → 부적합항목 텍스트로 세분 시도
    text = item.replace(" ", "")
    if "완전이탈" in text or "완전분리" in text:
        return Label.DETACHED_FULL.value
    if "이탈" in text or "분리" in text or "들뜸" in text:
        return Label.DETACHED_PARTIAL.value
    if "연통" in text and ("손상" in text or "부식" in text or "찌그" in text or "변형" in text):
        return Label.DAMAGED_PIPE.value
    if "실리콘" in text:
        return Label.DAMAGED_SILICONE.value

    # 세분 불가 → 사람이 마저 봐야 함
    return NEEDS_REVIEW
