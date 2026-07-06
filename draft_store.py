"""오류 후 다시 사용할 마지막 콘솔 입력을 로컬 JSON 파일에 보관합니다.

개인 링크와 사진 경로가 들어가므로 이 파일은 Git에 올리지 않고 사용자 PC에만
남깁니다.
"""

from __future__ import annotations

# 입력값을 한글이 유지되는 JSON으로 저장하고 다시 읽습니다.
import json
# 임시 입력 파일의 위치와 사진 경로를 안전하게 처리합니다.
from pathlib import Path
# JSON에서 읽은 값의 자료형을 검사할 때 사용합니다.
from typing import Any

# 프로젝트 기준 경로와 리뷰 입력 검증 기능을 재사용합니다.
from config import BASE_DIR
from post_generator import InputError, ReviewInput, validate_review


# 마지막 입력은 개인 데이터이므로 data 폴더에 로컬 파일로만 보관합니다.
LAST_INPUT_PATH = BASE_DIR / "data" / "last_input.json"
# 저장 파일에서 허용할 세 가지 생성 방식입니다.
VALID_MODES = {"chatgpt", "ollama", "openai", "layout"}


class DraftStoreError(Exception):
    """마지막 입력을 저장하거나 불러오거나 삭제하지 못했을 때 발생합니다."""


def save_last_input(mode: str, review: ReviewInput) -> None:
    """선택 모드와 리뷰 입력 전체를 다음 실행에서 복원할 JSON으로 저장합니다."""

    # 잘못된 내부 모드가 저장되어 다음 실행을 막지 않도록 먼저 확인합니다.
    if mode not in VALID_MODES:
        raise DraftStoreError(f"저장할 생성 방식이 올바르지 않습니다: {mode}")

    # Path 객체는 JSON에 직접 저장할 수 없으므로 전체 경로 문자열로 바꿉니다.
    payload = {
        "version": 1,
        "mode": mode,
        "review": {
            "review_type": review.review_type,
            "name": review.name,
            "link": review.link,
            "memo": review.memo,
            "rating": review.rating,
            "image_paths": [str(path) for path in review.image_paths],
        },
    }
    # 저장 중 중단돼 기존 파일까지 깨지는 일을 줄이기 위해 임시 파일을 사용합니다.
    temporary_path = LAST_INPUT_PATH.with_suffix(".tmp")
    try:
        # data 폴더가 삭제됐더라도 자동으로 다시 만듭니다.
        LAST_INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        # 사용자가 직접 확인할 수 있도록 들여쓰기된 UTF-8 JSON으로 기록합니다.
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 완전히 기록된 임시 파일로 기존 체크포인트를 한 번에 교체합니다.
        temporary_path.replace(LAST_INPUT_PATH)
    except OSError as exc:
        raise DraftStoreError(f"이전 입력을 임시 저장하지 못했습니다: {exc}") from exc


def load_last_input() -> tuple[str, ReviewInput] | None:
    """저장된 마지막 입력이 있으면 검증해 모드와 리뷰 객체로 반환합니다."""

    # 정상 종료 뒤 파일이 삭제된 상태는 오류가 아니라 새 입력 시작을 뜻합니다.
    if not LAST_INPUT_PATH.exists():
        return None

    try:
        # 한글 링크와 메모가 유지되도록 UTF-8 JSON으로 읽습니다.
        payload: Any = json.loads(LAST_INPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftStoreError(f"저장된 이전 입력을 읽지 못했습니다: {exc}") from exc

    # 예상한 최상위 객체와 버전인지 확인해 오래되거나 깨진 파일을 차단합니다.
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise DraftStoreError("저장된 이전 입력의 파일 형식이 올바르지 않습니다.")
    mode = payload.get("mode")
    review_data = payload.get("review")
    if mode not in VALID_MODES or not isinstance(review_data, dict):
        raise DraftStoreError("저장된 이전 입력의 생성 방식 또는 리뷰 정보가 없습니다.")

    # 필수 문자열과 사진 경로 배열의 자료형을 모델 호출 전에 확인합니다.
    string_fields = ("review_type", "name", "link", "memo")
    if not all(isinstance(review_data.get(field), str) for field in string_fields):
        raise DraftStoreError("저장된 이전 입력의 문자 항목이 올바르지 않습니다.")
    rating = review_data.get("rating")
    image_paths = review_data.get("image_paths")
    if (
        isinstance(rating, bool)
        or not isinstance(rating, (int, float))
        or not isinstance(image_paths, list)
        or not all(isinstance(path, str) for path in image_paths)
    ):
        raise DraftStoreError("저장된 이전 입력의 별점 또는 사진 경로가 올바르지 않습니다.")

    # 검증한 JSON 값을 프로그램의 공통 리뷰 객체로 복원합니다.
    review = ReviewInput(
        review_type=review_data["review_type"],
        name=review_data["name"],
        link=review_data["link"],
        memo=review_data["memo"],
        rating=float(rating),
        image_paths=[Path(path) for path in image_paths],
    )
    try:
        # Ollama와 OpenAI는 실제 사진이 필요하고 ChatGPT 수동 모드는 필요하지 않습니다.
        validate_review(review, require_images=(mode != "chatgpt"))
    except InputError as exc:
        raise DraftStoreError(f"저장된 이전 입력을 사용할 수 없습니다: {exc}") from exc
    return mode, review


def clear_last_input() -> None:
    """프로그램이 정상 완료되면 더 이상 필요 없는 임시 입력을 삭제합니다."""

    try:
        # 파일이 이미 없어도 정상 종료 처리는 성공한 것으로 봅니다.
        LAST_INPUT_PATH.unlink(missing_ok=True)
    except OSError as exc:
        raise DraftStoreError(f"임시 입력 파일을 삭제하지 못했습니다: {exc}") from exc
