"""네이버 내 템플릿의 표시를 사진 그룹과 작성 공간으로 연결합니다.

4번 모드는 사진을 분석하지 않고 사용자가 입력한 순서와 구간별 사진 수만으로
상품·가게 리뷰 템플릿을 채웁니다.
"""

from __future__ import annotations

# 템플릿에 채울 값들을 명확한 객체로 묶습니다.
from dataclasses import dataclass
# 사진 그룹에 들어갈 로컬 파일 경로를 다룹니다.
from pathlib import Path

# 공통 리뷰 입력 검증과 자료형을 재사용합니다.
from post_generator import InputError, ReviewInput, validate_review


@dataclass(frozen=True)
class TemplatePhotoSection:
    """템플릿 사진 표시 하나와 사용자에게 보여줄 구간 이름입니다."""

    # 네이버 내 템플릿에 한 줄로 입력할 고유 표시입니다.
    marker: str
    # 콘솔에서 몇 장인지 질문할 때 사용할 쉬운 구간 이름입니다.
    label: str


@dataclass(frozen=True)
class NaverTemplateLayout:
    """선택한 내 템플릿 이름과 각 표시를 교체할 내용입니다."""

    # 사용자가 네이버에 저장해둘 내 템플릿 이름입니다.
    template_name: str
    # 일반 텍스트 표시와 직접 작성할 안내 문구의 연결입니다.
    text_slots: dict[str, str]
    # 사진 표시와 순서가 유지된 실제 사진 목록의 연결입니다.
    photo_slots: dict[str, list[Path]]


# 상품 리뷰에서 배송 사진과 상세 사진을 구분할 표시입니다.
PRODUCT_PHOTO_SECTIONS = (
    TemplatePhotoSection("[[DELIVERY_PHOTOS]]", "배송·포장 사진"),
    TemplatePhotoSection("[[DETAIL_PHOTOS]]", "상품 상세·사용 사진"),
)
# 가게 리뷰에서 화면 캡처의 스티커 구간과 맞춘 네 가지 사진 표시입니다.
RESTAURANT_PHOTO_SECTIONS = (
    TemplatePhotoSection("[[EXTERIOR_PHOTOS]]", "외부 사진"),
    TemplatePhotoSection("[[INTERIOR_PHOTOS]]", "내부 사진"),
    TemplatePhotoSection("[[MENU_PHOTOS]]", "메뉴판 사진"),
    TemplatePhotoSection("[[FOOD_PHOTOS]]", "음식 사진"),
)


def get_photo_sections(review_type: str) -> tuple[TemplatePhotoSection, ...]:
    """리뷰 종류에 맞는 사진 구간 정의를 반환합니다."""

    if review_type == "product":
        return PRODUCT_PHOTO_SECTIONS
    if review_type == "restaurant":
        return RESTAURANT_PHOTO_SECTIONS
    raise InputError("네이버 템플릿에 사용할 리뷰 종류가 올바르지 않습니다.")


def build_naver_template_layout(
    review: ReviewInput,
    section_counts: list[int],
) -> NaverTemplateLayout:
    """입력 사진을 구간별 개수에 따라 나누고 템플릿 교체값을 만듭니다."""

    # 사진 파일과 공통 입력값을 브라우저를 열기 전에 모두 확인합니다.
    validate_review(review)
    sections = get_photo_sections(review.review_type)
    if len(section_counts) != len(sections):
        raise InputError("템플릿 사진 구간 개수가 올바르지 않습니다.")
    if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in section_counts):
        raise InputError("템플릿의 사진 수는 0 이상의 정수여야 합니다.")
    if sum(section_counts) != len(review.image_paths):
        raise InputError(
            "구간별 사진 수의 합계가 입력 사진 수와 일치하지 않습니다."
        )

    # 입력한 사진 순서를 유지하면서 앞 구간부터 필요한 개수만큼 잘라냅니다.
    photo_slots: dict[str, list[Path]] = {}
    cursor = 0
    for section, count in zip(sections, section_counts):
        photo_slots[section.marker] = review.image_paths[cursor : cursor + count]
        cursor += count

    if review.review_type == "restaurant":
        # 가게 템플릿의 고정 스티커 아래에는 사용자가 직접 다듬을 글감을 넣습니다.
        text_slots = {
            "[[INTRO]]": f"✏️ 방문 이유와 첫인상을 입력하세요.\n작성 메모: {review.memo}",
            "[[HOURS]]": "✏️ 영업시간과 휴무일을 입력하세요.",
            "[[LOCATION]]": (
                "✏️ 가까운 역, 출구와 찾아가는 방법을 입력하세요.\n"
                f"{review.link}"
            ),
            "[[FINAL]]": (
                "✏️ 맛, 가격, 만족도와 재방문 의사를 입력하세요.\n"
                f"별점 메모: {review.rating:g}/5"
            ),
        }
        template_name = "가게리뷰_자동"
    else:
        # 상품 템플릿은 구매 이유와 최종 사용 후기를 직접 작성할 공간을 제공합니다.
        text_slots = {
            "[[INTRO]]": f"✏️ 상품을 알게 된 계기를 입력하세요.\n작성 메모: {review.memo}",
            "[[PURCHASE_REASON]]": "✏️ 구매 이유와 구매 과정을 입력하세요.",
            "[[ONE_LINE]]": (
                "✏️ 장점, 아쉬운 점과 추천 대상을 입력하세요.\n"
                f"별점 메모: {review.rating:g}/5"
            ),
            "[[FINAL]]": f"✏️ 최종 한줄평을 입력하세요.\n{review.link}",
        }
        template_name = "상품리뷰_자동"

    return NaverTemplateLayout(
        template_name=template_name,
        text_slots=text_slots,
        photo_slots=photo_slots,
    )
