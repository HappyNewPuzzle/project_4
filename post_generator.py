"""입력 검증, 프롬프트 구성, 결과 저장을 담당합니다.

콘솔이나 API 통신과 분리된 핵심 로직이므로 나중에 GUI에서도 재사용할 수 있습니다.
"""

from __future__ import annotations

# 파일명에 사용할 수 없는 문자를 찾고 바꿉니다.
import re
# 리뷰 입력과 결과를 명확한 자료형으로 묶습니다.
from dataclasses import dataclass
# 결과 파일명에 현재 날짜와 시간을 넣습니다.
from datetime import datetime
# 사진, 프롬프트, 출력 파일의 경로를 처리합니다.
from pathlib import Path

# 공통 경로는 config.py에 정의된 값을 재사용합니다.
from config import OUTPUT_DIR, PROMPTS_DIR
# 실제 API 통신은 전용 OpenAI 클라이언트에 맡깁니다.
from openai_client import BlogOpenAIClient


# OpenAI Vision이 입력으로 받을 수 있는 이미지 확장자입니다.
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
# 내부 리뷰 종류와 해당 프롬프트 파일명을 연결합니다.
TEMPLATE_FILES = {
    "restaurant": "restaurant_review.txt",
    "product": "product_review.txt",
}


class InputError(Exception):
    """사용자 입력값이 올바르지 않을 때 발생합니다."""


class SaveError(Exception):
    """생성 결과 파일을 저장하지 못했을 때 발생합니다."""


@dataclass(frozen=True)
class ReviewInput:
    """사용자가 입력한 리뷰 정보를 담는 읽기 전용 객체입니다."""

    # restaurant 또는 product 중 선택된 리뷰 종류입니다.
    review_type: str
    # 음식점명 또는 상품명입니다.
    name: str
    # 지도 또는 구매 페이지 주소입니다.
    link: str
    # 리뷰에서 강조할 사용자의 핵심 경험입니다.
    memo: str
    # 1점 이상 5점 이하의 만족도입니다.
    rating: float
    # Vision으로 분석할 로컬 사진 경로 목록입니다.
    image_paths: list[Path]


@dataclass(frozen=True)
class GeneratedPost:
    """OpenAI가 만든 최종 블로그 결과를 담는 읽기 전용 객체입니다."""

    # 사용자가 선택할 다섯 개 제목입니다.
    title_candidates: list[str]
    # 네이버 블로그 편집기에 복사할 본문입니다.
    body: str
    # 해시 기호를 붙이기 전의 열 개 태그입니다.
    tags: list[str]


def validate_review(review: ReviewInput) -> None:
    """API 비용이 발생하기 전에 사용자 입력 전체를 검사합니다."""

    # 지원하는 두 종류 외의 리뷰 코드는 처리하지 않습니다.
    if review.review_type not in TEMPLATE_FILES:
        raise InputError("리뷰 종류가 올바르지 않습니다.")
    # 공백만 입력된 이름은 허용하지 않습니다.
    if not review.name.strip():
        raise InputError("이름을 입력해주세요.")
    # 본문에 포함할 링크가 비어 있지 않은지 확인합니다.
    if not review.link.strip():
        raise InputError("링크를 입력해주세요.")
    # 리뷰의 핵심 재료인 한줄 메모를 반드시 받습니다.
    if not review.memo.strip():
        raise InputError("한줄 메모를 입력해주세요.")
    # 소수점 별점을 포함해 1부터 5 사이만 허용합니다.
    if not 1 <= review.rating <= 5:
        raise InputError("별점은 1점부터 5점 사이로 입력해주세요.")
    # Vision 분석을 위해 사진을 최소 한 장 요구합니다.
    if not review.image_paths:
        raise InputError("사진 경로를 한 개 이상 입력해주세요.")

    # 여러 사진을 하나씩 순회하며 실제 파일과 확장자를 검사합니다.
    for path in review.image_paths:
        # 경로가 존재하고 일반 파일인 경우에만 사진으로 사용합니다.
        if not path.exists() or not path.is_file():
            raise InputError(f"사진 파일을 찾을 수 없습니다: {path}")
        # 확장자의 대소문자를 무시하고 지원 형식과 비교합니다.
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            # 오류 메시지에 허용 형식을 함께 표시합니다.
            allowed = ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
            raise InputError(f"지원하지 않는 사진 형식입니다: {path} (지원: {allowed})")


def _load_template(review_type: str) -> str:
    """선택한 리뷰 종류에 맞는 프롬프트 파일을 읽습니다."""

    # 리뷰 종류를 파일명으로 바꿔 prompts 폴더의 전체 경로를 만듭니다.
    template_path = PROMPTS_DIR / TEMPLATE_FILES[review_type]
    try:
        # 한글 프롬프트가 깨지지 않도록 UTF-8로 읽습니다.
        return template_path.read_text(encoding="utf-8")
    except OSError as exc:
        # 누락과 권한 오류를 사용자가 이해하기 쉬운 입력 오류로 바꿉니다.
        raise InputError(f"프롬프트 파일을 읽을 수 없습니다: {exc}") from exc


def generate_post(
    review: ReviewInput,
    settings: dict[str, str],
    client: BlogOpenAIClient,
) -> GeneratedPost:
    """입력 정보와 사진으로 하나의 블로그 글을 생성합니다."""

    # 잘못된 입력으로 API 비용이 발생하지 않도록 가장 먼저 검사합니다.
    validate_review(review)
    # 음식점 또는 상품에 맞는 글 구조를 파일에서 읽습니다.
    template = _load_template(review.review_type)

    # 개인 스타일 설정을 모델이 읽기 쉬운 글머리표 문자열로 바꿉니다.
    style = "\n".join(f"- {key}: {value}" for key, value in settings.items())
    # 템플릿, 개인 스타일, 사실성 원칙을 하나의 고정 지침으로 합칩니다.
    instructions = (
        f"{template}\n\n"
        "[블로그 스타일 설정]\n"
        f"{style}\n\n"
        "[공통 작성 원칙]\n"
        "- 사용자가 주지 않았고 사진에서도 확인할 수 없는 사실은 만들지 마세요.\n"
        "- 사진마다 눈에 보이는 특징을 간단히 파악해 본문 흐름에 자연스럽게 반영하세요.\n"
        "- 사진 파일명이나 'AI 분석'이라는 표현은 본문에 쓰지 마세요.\n"
        "- 광고성 과장 표현은 피하고 실제 개인 후기처럼 작성하세요.\n"
        "- 설정의 opening과 closing 문구를 본문에 각각 한 번 사용하세요.\n"
        "- 설정의 link_text 다음 줄에 사용자가 제공한 링크를 그대로 한 번 넣으세요.\n"
        "- 태그에는 # 기호를 붙이지 마세요."
    )
    # 내부 영문 코드를 모델이 이해하기 쉬운 한국어 종류로 바꿉니다.
    kind = "음식점" if review.review_type == "restaurant" else "상품"
    # 매번 달라지는 실제 리뷰 정보는 사용자 프롬프트로 구성합니다.
    user_prompt = (
        "[리뷰 정보]\n"
        f"- 종류: {kind} 리뷰\n"
        f"- 이름: {review.name}\n"
        f"- 링크: {review.link}\n"
        f"- 한줄 메모: {review.memo}\n"
        f"- 별점: {review.rating:g}/5\n"
        f"- 사진 수: {len(review.image_paths)}장\n\n"
        "위 정보와 첨부 사진을 바탕으로 한국어 네이버 블로그 리뷰 초안을 작성해주세요."
    )

    # 준비된 지침과 모든 사진을 OpenAI 클라이언트에 전달합니다.
    raw = client.generate_post(instructions, user_prompt, review.image_paths)
    # 응답에서 제목, 본문, 태그를 각각 꺼냅니다.
    titles = raw.get("title_candidates")
    body = raw.get("body")
    tags = raw.get("tags")
    # 구조화 출력과 별개로 프로그램에서도 자료형과 개수를 다시 확인합니다.
    if (
        not isinstance(titles, list)
        or len(titles) != 5
        or not all(isinstance(item, str) for item in titles)
        or not isinstance(body, str)
        or not isinstance(tags, list)
        or len(tags) != 10
        or not all(isinstance(item, str) for item in tags)
    ):
        raise InputError("생성된 글의 형식이 올바르지 않습니다.")

    # 모델이 붙인 # 문자와 앞뒤 공백을 제거해 태그 형식을 통일합니다.
    cleaned_tags = [tag.strip().lstrip("#") for tag in tags]
    # 제목과 본문의 가장자리 공백도 정리한 최종 객체를 반환합니다.
    return GeneratedPost(
        title_candidates=[title.strip() for title in titles],
        body=body.strip(),
        tags=cleaned_tags,
    )


def format_post(post: GeneratedPost) -> str:
    """콘솔과 TXT 파일에 공통으로 사용할 결과 문자열을 만듭니다."""

    # 다섯 제목 앞에 1부터 시작하는 번호를 붙입니다.
    titles = "\n".join(
        f"{index}. {title}" for index, title in enumerate(post.title_candidates, 1)
    )
    # 각 태그 앞에 #을 붙여 네이버에 바로 복사할 한 줄을 만듭니다.
    tags = " ".join(f"#{tag}" for tag in post.tags)
    # 제목, 본문, 태그 영역을 빈 줄과 구분 제목으로 합칩니다.
    return (
        "=== 제목 후보 5개 ===\n"
        f"{titles}\n\n"
        "=== 블로그 본문 ===\n"
        f"{post.body}\n\n"
        "=== 네이버 블로그 태그 10개 ===\n"
        f"{tags}\n"
    )


def save_post(post: GeneratedPost, review_name: str) -> Path:
    """생성 결과를 시간과 리뷰 이름이 포함된 TXT 파일로 저장합니다."""

    # Windows 파일명에 금지된 문자와 제어 문자를 밑줄로 바꿉니다.
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", review_name).strip(" ._")
    # 파일명이 너무 길거나 완전히 비는 경우를 방지합니다.
    safe_name = safe_name[:50] or "review"
    # 같은 리뷰도 덮어쓰지 않도록 현재 시각을 파일명에 붙입니다.
    filename = f"{datetime.now():%Y%m%d_%H%M%S}_{safe_name}.txt"
    # 출력 폴더와 안전한 파일명을 결합합니다.
    output_path = OUTPUT_DIR / filename

    try:
        # 출력 폴더가 없어졌다면 실행 중 자동으로 다시 만듭니다.
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # 한글과 이모티콘이 유지되도록 UTF-8로 저장합니다.
        output_path.write_text(format_post(post), encoding="utf-8")
    except OSError as exc:
        # 권한이나 디스크 문제를 프로그램 전용 저장 오류로 바꿉니다.
        raise SaveError(f"파일 저장에 실패했습니다: {exc}") from exc

    # 메인 화면에서 저장 위치를 보여줄 수 있도록 경로를 반환합니다.
    return output_path
