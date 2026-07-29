"""
yesco-inspection-sampler 의 3단계 판정(정상/의심/부적합) + 자유 텍스트 defect_item
   → yesco-ai-engine 의 5-클래스 라벨 스키마(docs/guides/labeling_guide_v0.1.md) 매핑

⚠️ 주의: defect_item 은 SAP/현장 입력 자유 텍스트라 실제 값 예시를 아직 확보하지 못했다.
   아래 KEYWORD_RULES 는 라벨링 가이드 문서(v0.1)의 용어를 기준으로 한 1차 추정 규칙이다.
   실제 defect_item 텍스트 예시가 확보되면 KEYWORD_RULES 를 보강해야 한다.

   매핑이 애매하거나 규칙에 걸리지 않는 건은 label="UNCLEAR", needs_review=True 로
   표시되며, dataset_builder 가 `unmapped_defect_items.csv` 로 별도 정리해준다.
   → 팀에서 이 파일을 보고 실제 defect_item 값을 확인해 KEYWORD_RULES 를 채워 넣으면 된다.
"""
from dataclasses import dataclass
from typing import Optional

# 5-클래스 라벨 (docs/guides/labeling_guide_v0.1.md 기준)
LABEL_NORMAL = "NORMAL"
LABEL_DAMAGED_SILICONE = "DAMAGED_SILICONE"
LABEL_DAMAGED_PIPE = "DAMAGED_PIPE"
LABEL_DETACHED_PARTIAL = "DETACHED_PARTIAL"
LABEL_DETACHED_FULL = "DETACHED_FULL"
LABEL_UNCLEAR = "UNCLEAR"
LABEL_EXCLUDED = "EXCLUDED"

URGENCY_NONE = "NONE"
URGENCY_SCHEDULED = "SCHEDULED"
URGENCY_URGENT = "URGENT"
URGENCY_IMMEDIATE = "IMMEDIATE"

# 라벨별 기본 긴급도 (가이드 문서의 클래스 요약표 기준)
DEFAULT_URGENCY = {
    LABEL_NORMAL: URGENCY_NONE,
    LABEL_DAMAGED_SILICONE: URGENCY_SCHEDULED,
    LABEL_DAMAGED_PIPE: URGENCY_URGENT,
    LABEL_DETACHED_PARTIAL: URGENCY_URGENT,
    LABEL_DETACHED_FULL: URGENCY_IMMEDIATE,
    LABEL_UNCLEAR: URGENCY_NONE,
    LABEL_EXCLUDED: URGENCY_NONE,
}

# 원칙 2(복합 결함 → 가장 심각한 쪽) 를 반영하기 위한 심각도 순서
SEVERITY_ORDER = [
    LABEL_NORMAL,
    LABEL_DAMAGED_SILICONE,
    LABEL_DAMAGED_PIPE,
    LABEL_DETACHED_PARTIAL,
    LABEL_DETACHED_FULL,
]

# defect_item / comment 텍스트에서 라벨을 추정하기 위한 키워드 규칙
# (우선순위 순서대로 검사 — 위에 있을수록 더 심각한 것으로 간주해 먼저 매칭)
KEYWORD_RULES: list[tuple[str, list[str]]] = [
    (LABEL_DETACHED_FULL, ["완전이탈", "완전 이탈", "완전분리", "완전 분리", "탈락"]),
    (LABEL_DETACHED_PARTIAL, [
        "이탈", "분리", "이격", "틈", "갭", "들뜸", "들뜬", "빠짐", "빠져",
    ]),
    (LABEL_DAMAGED_PIPE, [
        "부식", "녹", "찌그러", "변형", "균열", "구멍", "그을음", "손상",
        "파손", "깨짐", "부러", "천공",
    ]),
    (LABEL_DAMAGED_SILICONE, [
        "실리콘", "코킹", "충전재", "마모", "박리", "노후",
    ]),
    (LABEL_EXCLUDED, [
        "가스레인지", "레인지", "대상아님", "해당없음", "촬영불가", "미설치",
    ]),
    (LABEL_UNCLEAR, [
        "불명확", "확인불가", "어두움", "흐림", "판독불가",
    ]),
]


@dataclass
class MappedLabel:
    label: str
    urgency: str
    confidence: str          # HIGH / MEDIUM / LOW
    needs_review: bool       # True면 사람이 다시 확인해야 함 (규칙이 애매했던 경우)
    matched_keyword: Optional[str] = None
    reason: str = ""


def _match_keywords(text: str) -> tuple[Optional[str], Optional[str]]:
    """text 안에서 KEYWORD_RULES 순서대로 첫 매칭 라벨/키워드를 찾는다."""
    if not text:
        return None, None
    lowered = text.replace(" ", "")
    for label, keywords in KEYWORD_RULES:
        for kw in keywords:
            if kw.replace(" ", "") in lowered:
                return label, kw
    return None, None


def map_verdict_to_label(
    verdict: Optional[str],
    defect_item: Optional[str] = None,
    comment: Optional[str] = None,
    has_defect_points: bool = False,
) -> MappedLabel:
    """
    sampler 의 (verdict, defect_item, comment, defect_points 유무) →
    yesco-ai-engine 5-클래스 라벨로 변환.

    Args:
        verdict: "정상" / "의심" / "부적합" (ReviewViewer 판정)
        defect_item: SAP/현장에서 넘어온 자유 텍스트 결함 항목 (있을 수도, 없을 수도 있음)
        comment: 검토자가 남긴 코멘트
        has_defect_points: 뷰어에서 문제 부위를 클릭으로 표시했는지 여부
                            (표시했으면 사람이 실제로 위치를 특정한 것이므로 신뢰도 상승)

    Returns:
        MappedLabel
    """
    verdict = (verdict or "").strip()

    # 1) 정상 판정은 바로 NORMAL
    if verdict == "정상":
        return MappedLabel(
            label=LABEL_NORMAL,
            urgency=URGENCY_NONE,
            confidence="HIGH",
            needs_review=False,
            reason="verdict=정상",
        )

    # 2) 의심/부적합 → defect_item, comment 순으로 키워드 매칭 시도
    label, kw = _match_keywords(defect_item or "")
    reason = f"defect_item 키워드 매칭: '{kw}'" if kw else ""

    if label is None:
        label, kw = _match_keywords(comment or "")
        reason = f"comment 키워드 매칭: '{kw}'" if kw else ""

    if label is None:
        # 키워드 매칭 실패 → 사람이 표시한 클릭 포인트가 있으면 최소한 "결함 있음"은 확실하므로
        # 안전 우선 원칙(가이드 원칙 1)에 따라 더 심각할 수 있는 DETACHED_PARTIAL 로 잠정 분류하고
        # needs_review=True 로 표시해 사람이 재확인하도록 한다.
        if has_defect_points:
            return MappedLabel(
                label=LABEL_DETACHED_PARTIAL,
                urgency=DEFAULT_URGENCY[LABEL_DETACHED_PARTIAL],
                confidence="LOW",
                needs_review=True,
                reason="키워드 매칭 실패 + 클릭 표시 존재 → 잠정 DETACHED_PARTIAL (재확인 필요)",
            )
        return MappedLabel(
            label=LABEL_UNCLEAR,
            urgency=URGENCY_NONE,
            confidence="LOW",
            needs_review=True,
            reason="키워드 매칭 실패, 클릭 표시도 없음 → UNCLEAR (재확인 필요)",
        )

    confidence = "HIGH" if (kw and has_defect_points) else ("MEDIUM" if kw else "LOW")
    return MappedLabel(
        label=label,
        urgency=DEFAULT_URGENCY.get(label, URGENCY_NONE),
        confidence=confidence,
        needs_review=False,
        matched_keyword=kw,
        reason=reason,
    )
