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
# OpenAI와 Ollama 클라이언트가 따라야 할 공통 형태를 정의합니다.
from typing import Any, Protocol

# 공통 경로는 config.py에 정의된 값을 재사용합니다.
from config import OUTPUT_DIR, PROMPT_OUTPUT_DIR, PROMPTS_DIR


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


class BlogGenerationClient(Protocol):
    """OpenAI와 Ollama 클라이언트가 공통으로 제공해야 하는 기능입니다."""

    def generate_post(
        self, instructions: str, user_prompt: str, image_paths: list[Path]
    ) -> dict[str, Any]:
        """프롬프트와 사진을 받아 블로그 글 딕셔너리를 반환합니다."""


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
    """선택한 AI 모델이 만든 최종 블로그 결과를 담는 읽기 전용 객체입니다."""

    # 사용자가 선택할 다섯 개 제목입니다.
    title_candidates: list[str]
    # 네이버 블로그 편집기에 복사할 본문입니다.
    body: str
    # 해시 기호를 붙이기 전의 열 개 태그입니다.
    tags: list[str]


def create_layout_post(
    review: ReviewInput,
    settings: dict[str, str],
) -> GeneratedPost:
    """AI 호출 없이 사진과 직접 작성할 안내 문구가 포함된 빈 초안을 만듭니다."""

    # 사진 파일까지 미리 확인해 네이버 배치 도중 뒤늦게 실패하지 않게 합니다.
    validate_review(review)
    # 리뷰 종류에 맞춰 사진 뒤에 사용자가 채울 글감 항목을 준비합니다.
    if review.review_type == "restaurant":
        section_prompts = [
            "✏️ 방문 이유와 매장의 첫인상을 입력하세요.",
            "✏️ 메뉴와 분위기에 대한 내용을 입력하세요.",
            "✏️ 맛과 가격에 대한 솔직한 후기를 입력하세요.",
            "✏️ 만족도와 재방문 의사를 입력하세요.",
        ]
        kind_title = "방문"
    else:
        section_prompts = [
            "✏️ 구매 이유와 제품의 첫인상을 입력하세요.",
            "✏️ 제품 특징과 사용 후기를 입력하세요.",
            "✏️ 장점과 아쉬운 점을 입력하세요.",
            "✏️ 추천 대상과 최종 만족도를 입력하세요.",
        ]
        kind_title = "사용"

    # 시작 인사 다음에 사용자가 입력한 메모를 글 작성 참고란으로 남깁니다.
    body_parts = [
        settings["opening"],
        f"✏️ 작성 메모: {review.memo}",
        section_prompts[0],
    ]
    # 사진은 사용자가 입력한 순서를 바꾸지 않고 각각 설명 공간과 함께 배치합니다.
    for index in range(1, len(review.image_paths) + 1):
        body_parts.extend(
            [
                f"[PHOTO_{index}]",
                f"✏️ 사진 {index} 설명을 입력하세요.",
            ]
        )
    # 사진 뒤에는 종류별 후기 항목과 링크·마무리 틀을 차례대로 추가합니다.
    body_parts.extend(
        [
            *section_prompts[1:],
            settings["link_text"],
            review.link,
            settings["closing"],
        ]
    )
    # AI가 없어도 선택 가능한 제목과 기본 태그를 사용자 정보만으로 만듭니다.
    title_candidates = [
        f"{review.name} {kind_title} 후기",
        f"{review.name} 솔직 리뷰",
        f"사진으로 남기는 {review.name} 후기",
        f"{review.name} 직접 경험한 기록",
        f"{review.name} 리뷰 정리",
    ]
    return GeneratedPost(
        title_candidates=title_candidates,
        body="\n\n".join(body_parts),
        tags=_complete_tags([], review),
    )


def validate_review(review: ReviewInput, require_images: bool = True) -> None:
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
    if require_images and not review.image_paths:
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


def build_generation_prompts(
    review: ReviewInput,
    settings: dict[str, str],
    require_images: bool = True,
) -> tuple[str, str]:
    """모든 AI 제공자가 공유할 고정 지침과 사용자 프롬프트를 만듭니다."""

    # 잘못된 입력으로 모델 호출이나 수동 작업이 시작되지 않도록 먼저 검사합니다.
    validate_review(review, require_images=require_images)
    # 음식점 또는 상품에 맞는 글 구조를 파일에서 읽습니다.
    template = _load_template(review.review_type)

    # 개인 스타일 설정을 모델이 읽기 쉬운 글머리표 문자열로 바꿉니다.
    style = "\n".join(f"- {key}: {value}" for key, value in settings.items())
    if review.image_paths:
        # API 모드는 입력 사진 수를 아니까 모든 위치 표시를 실제 문자열로 나열합니다.
        photo_marker_checklist = ", ".join(
            f"[PHOTO_{index}]" for index in range(1, len(review.image_paths) + 1)
        )
        photo_rules = (
            f"- 본문에는 [PHOTO_1]부터 [PHOTO_{len(review.image_paths)}]까지의 표시를 "
            "사진 입력 순서대로 각각 정확히 한 번씩, 별도의 한 줄로 넣으세요.\n"
            f"- 반드시 모두 포함할 사진 표시 체크리스트: {photo_marker_checklist}\n"
        )
        photo_count = f"- 사진 수: {len(review.image_paths)}장"
    else:
        # ChatGPT 수동 모드는 사용자가 대화창에 직접 첨부한 사진 수를 모델이 세게 합니다.
        photo_rules = (
            "- 이 프롬프트와 함께 ChatGPT 대화창에 첨부된 모든 사진을 분석하세요.\n"
            "- 본문에는 [PHOTO_1]부터 시작해 첨부된 사진 수만큼의 표시를 "
            "첨부 순서대로 각각 정확히 한 번씩, 별도의 한 줄로 넣으세요.\n"
        )
        photo_count = "- 사진: 이 프롬프트와 함께 ChatGPT에 직접 첨부한 사진 전체"
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
        "- 별점이 낮거나 보통이면 만족도와 재방문 의사도 그 수준에 맞추세요.\n"
        "- 사용자가 말하지 않은 방문 동행, 방문 이유, 주문 메뉴, 가격, 맛, "
        "서비스 경험은 사진만 보고 만들지 마세요.\n"
        "- 사진으로는 보이는 외형과 분위기만 설명하고 실제 맛이나 가격을 단정하지 마세요.\n"
        "- 링크는 Markdown 문법을 쓰지 말고 원본 URL을 일반 텍스트로 넣으세요.\n"
        f"{photo_rules}"
        "- 각 [PHOTO_N] 바로 다음에는 해당 N번 사진에서 확실히 보이는 내용만 설명하세요.\n"
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
        f"{photo_count}\n\n"
        "위 정보와 첨부 사진을 바탕으로 한국어 네이버 블로그 리뷰 초안을 작성해주세요."
    )
    # 제공자별 클라이언트가 같은 프롬프트를 사용하도록 두 문자열을 함께 반환합니다.
    return instructions, user_prompt


def build_chatgpt_prompt(
    review: ReviewInput, settings: dict[str, str]
) -> str:
    """사진과 함께 ChatGPT에 직접 붙여넣을 완성 프롬프트를 만듭니다."""

    # API와 동일한 리뷰 구조 및 개인 스타일 지침을 재사용합니다.
    instructions, user_prompt = build_generation_prompts(
        review,
        settings,
        require_images=False,
    )
    # 경로를 받지 않는 수동 모드에서는 ChatGPT가 실제 첨부 사진 전체를 확인합니다.
    photo_request = (
        f"이 메시지와 함께 첨부한 사진 {len(review.image_paths)}장도 분석해주세요."
        if review.image_paths
        else "이 메시지와 함께 ChatGPT에 첨부한 모든 사진도 분석해주세요."
    )
    # 수동 모드에서는 JSON 대신 사람이 바로 복사할 수 있는 일반 텍스트를 요청합니다.
    return (
        "아래 작성 규칙과 리뷰 정보를 모두 반영해 결과만 작성해주세요.\n"
        f"{photo_request}\n\n"
        "=== 작성 규칙 ===\n"
        f"{instructions}\n\n"
        "=== 사용자 리뷰 정보 ===\n"
        f"{user_prompt}\n\n"
        "=== 출력 형식 ===\n"
        "=== 제목 후보 5개 ===\n"
        "1. 제목\n2. 제목\n3. 제목\n4. 제목\n5. 제목\n\n"
        "=== 블로그 본문 ===\n"
        "완성된 본문\n\n"
        "=== 네이버 블로그 태그 10개 ===\n"
        "#태그1 #태그2 #태그3 #태그4 #태그5 #태그6 #태그7 #태그8 #태그9 #태그10\n\n"
        "JSON이나 코드 블록을 사용하지 말고 위 형식의 한국어 결과만 출력해주세요."
    )


def _unique_nonempty_strings(value: Any) -> list[str]:
    """모델의 배열에서 비어 있지 않은 문자열만 순서를 유지해 가져옵니다."""

    # 배열이 아니면 호출한 쪽에서 기본 후보를 사용하도록 빈 목록을 반환합니다.
    if not isinstance(value, list):
        return []

    # 같은 제목이나 태그가 반복돼도 한 번만 남기기 위한 결과 목록입니다.
    cleaned: list[str] = []
    for item in value:
        # 문자열이 아닌 객체나 숫자는 블로그 결과로 사용하지 않습니다.
        if not isinstance(item, str):
            continue
        # 앞뒤 공백과 태그 앞의 해시 기호를 제거합니다.
        text = item.strip().lstrip("#").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _complete_titles(titles: Any, review: ReviewInput) -> list[str]:
    """모델 제목이 다섯 개보다 적거나 많아도 정확히 다섯 개로 보정합니다."""

    # 모델이 정상적으로 만든 고유 제목부터 최대 다섯 개까지 사용합니다.
    completed = _unique_nonempty_strings(titles)[:5]
    # 부족한 경우에만 사용자 입력을 근거로 한 안전한 제목 후보를 사용합니다.
    fallback_titles = [
        f"{review.name} 솔직 후기",
        f"{review.name} 사진으로 남긴 리뷰",
        f"{review.name} 직접 살펴본 후기",
        f"{review.name} 별점 {review.rating:g}점 리뷰",
        f"{review.name} 리뷰와 사진 기록",
    ]
    for fallback in fallback_titles:
        if len(completed) == 5:
            break
        if fallback not in completed:
            completed.append(fallback)
    return completed


def _complete_tags(tags: Any, review: ReviewInput) -> list[str]:
    """모델 태그의 중복과 개수 오류를 정리해 정확히 열 개로 보정합니다."""

    # 모델이 정상적으로 만든 고유 태그부터 최대 열 개까지 사용합니다.
    completed = _unique_nonempty_strings(tags)[:10]
    # 공백 없는 이름 태그와 리뷰 종류에 맞는 일반 태그를 준비합니다.
    name_tag = re.sub(r"\s+", "", review.name)
    if review.review_type == "restaurant":
        fallback_tags = [
            name_tag,
            "음식점리뷰",
            "방문후기",
            "사진리뷰",
            "솔직후기",
            "맛집기록",
            "일상기록",
            "후기공유",
            "리뷰추천",
            "블로그리뷰",
        ]
    else:
        fallback_tags = [
            name_tag,
            "상품리뷰",
            "사용후기",
            "사진리뷰",
            "솔직후기",
            "구매후기",
            "제품추천",
            "후기공유",
            "리뷰추천",
            "블로그리뷰",
        ]
    # 모델 태그가 부족한 만큼만 안전한 기본 태그로 채웁니다.
    for fallback in fallback_tags:
        if len(completed) == 10:
            break
        if fallback and fallback not in completed:
            completed.append(fallback)
    return completed


def _normalize_body(body: Any) -> str:
    """Qwen이 본문을 문단 배열로 반환해도 하나의 본문 문자열로 합칩니다."""

    # 정상적인 문자열 본문은 앞뒤 공백만 제거해 그대로 사용합니다.
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, list):
        # 문자열인 문단만 가져오고 빈 문단은 제거합니다.
        paragraphs = [
            paragraph.strip()
            for paragraph in body
            if isinstance(paragraph, str) and paragraph.strip()
        ]
        # 네이버 모바일 화면에서 읽기 좋도록 문단 사이를 빈 줄로 연결합니다.
        return "\n\n".join(paragraphs)
    # 그 밖의 객체나 숫자는 본문으로 안전하게 변환할 수 없습니다.
    return ""


def generate_post(
    review: ReviewInput,
    settings: dict[str, str],
    client: BlogGenerationClient,
) -> GeneratedPost:
    """입력 정보와 사진으로 OpenAI 또는 Ollama 블로그 글을 생성합니다."""

    # 두 AI 제공자에서 함께 사용할 지침과 사용자 정보를 만듭니다.
    instructions, user_prompt = build_generation_prompts(review, settings)
    # 준비된 지침과 모든 사진을 선택한 AI 클라이언트에 전달합니다.
    raw = client.generate_post(instructions, user_prompt, review.image_paths)
    # 응답에서 제목, 본문, 태그를 각각 꺼냅니다.
    # Qwen이 가끔 `title_candidates` 대신 `title` 또는 `titles`를 사용해도 복구합니다.
    titles = raw.get("title_candidates")
    if titles is None:
        titles = raw.get("title", raw.get("titles"))
    # Qwen이 본문을 문자열 배열로 반환하는 경우 하나의 본문으로 합칩니다.
    body = _normalize_body(raw.get("body"))
    tags = raw.get("tags")
    # 본문은 대체할 수 없는 핵심 결과이므로 문자열이며 내용이 있을 때만 사용합니다.
    if not body:
        raise InputError(
            "Ollama가 블로그 본문을 반환하지 않았습니다. "
            "제목·태그 개수 오류는 자동 보정되지만 빈 본문은 보정할 수 없습니다."
        )

    # 제목과 태그의 부족·초과·중복은 GPU 결과를 버리지 않고 로컬에서 보정합니다.
    completed_titles = _complete_titles(titles, review)
    completed_tags = _complete_tags(tags, review)
    # 보정된 제목·본문·태그를 최종 결과 객체로 반환합니다.
    return GeneratedPost(
        title_candidates=completed_titles,
        body=body,
        tags=completed_tags,
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


def _safe_review_name(review_name: str) -> str:
    """리뷰 이름을 Windows에서 안전한 짧은 파일명 조각으로 바꿉니다."""

    # Windows 파일명에 금지된 문자와 제어 문자를 밑줄로 바꿉니다.
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", review_name).strip(" ._")
    # 파일명이 너무 길거나 완전히 비는 경우를 방지합니다.
    return safe_name[:50] or "review"


def save_post(post: GeneratedPost, review_name: str) -> Path:
    """생성 결과를 시간과 리뷰 이름이 포함된 TXT 파일로 저장합니다."""

    # 공통 파일명 정리 함수를 사용해 안전한 이름을 만듭니다.
    safe_name = _safe_review_name(review_name)
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


def save_chatgpt_prompt(prompt: str, review: ReviewInput) -> Path:
    """ChatGPT용 프롬프트와 첨부할 사진 목록을 TXT 파일로 저장합니다."""

    # 사용자가 ChatGPT에 올릴 사진을 헷갈리지 않도록 번호와 경로를 기록합니다.
    if review.image_paths:
        # 이전에 경로가 포함된 리뷰 객체를 넘겨도 사진 체크리스트를 계속 지원합니다.
        image_list = "\n".join(
            f"{index}. {path}" for index, path in enumerate(review.image_paths, 1)
        )
        photo_guide = (
            "1. 아래 사진을 ChatGPT 대화창에 모두 첨부하세요.\n"
            "2. 클립보드에 복사된 프롬프트를 붙여넣고 전송하세요.\n\n"
            "=== 첨부할 사진 ===\n"
            f"{image_list}\n\n"
        )
    else:
        # 현재 수동 모드는 경로 대신 사용자가 고른 사진을 ChatGPT에 직접 첨부합니다.
        photo_guide = (
            "1. 리뷰에 사용할 사진을 ChatGPT 대화창에 원하는 순서대로 첨부하세요.\n"
            "2. 클립보드에 복사된 프롬프트를 붙여넣고 전송하세요.\n\n"
        )
    # 저장 파일에는 간단한 사용 순서와 실제 프롬프트를 함께 넣습니다.
    file_content = (
        "=== 사용 방법 ===\n"
        f"{photo_guide}"
        "=== ChatGPT에 붙여넣을 프롬프트 ===\n"
        f"{prompt}\n"
    )
    # Windows에서 사용할 수 있는 안전한 리뷰 이름을 만듭니다.
    safe_name = _safe_review_name(review.name)
    # 생성 시각을 포함해 기존 프롬프트 파일을 덮어쓰지 않게 합니다.
    filename = f"{datetime.now():%Y%m%d_%H%M%S}_{safe_name}_prompt.txt"
    # 프롬프트 전용 출력 폴더와 파일명을 결합합니다.
    output_path = PROMPT_OUTPUT_DIR / filename

    try:
        # 출력 폴더가 없으면 자동으로 생성합니다.
        PROMPT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # 한글과 이모티콘을 보존하는 UTF-8 텍스트로 저장합니다.
        output_path.write_text(file_content, encoding="utf-8")
    except OSError as exc:
        # 디스크나 권한 문제를 공통 저장 오류로 바꿉니다.
        raise SaveError(f"프롬프트 파일 저장에 실패했습니다: {exc}") from exc

    # 메인 화면에서 저장 위치를 알려줄 수 있도록 경로를 반환합니다.
    return output_path
