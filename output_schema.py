"""OpenAI와 Ollama가 공통으로 사용할 블로그 글 출력 구조입니다.

두 제공자가 같은 JSON 형식으로 응답하게 만들면 글 검증과 저장 코드를
한 번만 작성해도 되므로, 출력 규칙을 별도 파일에서 관리합니다.
"""

from __future__ import annotations

# JSON Schema 딕셔너리에 여러 자료형의 값이 들어가므로 Any를 사용합니다.
from typing import Any


# 모델이 반드시 지켜야 하는 최종 블로그 글 응답 구조입니다.
BLOG_POST_SCHEMA: dict[str, Any] = {
    # 최상위 응답은 JSON 객체여야 합니다.
    "type": "object",
    # 제목, 본문, 태그 각각의 자료형과 개수를 지정합니다.
    "properties": {
        "title_candidates": {
            "type": "array",
            "items": {"type": "string"},
            # 제목 후보는 정확히 다섯 개로 제한합니다.
            "minItems": 5,
            "maxItems": 5,
        },
        # 본문은 복사 가능한 하나의 긴 문자열입니다.
        "body": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            # 네이버 블로그 태그는 정확히 열 개로 제한합니다.
            "minItems": 10,
            "maxItems": 10,
        },
    },
    # 세 필드 중 하나라도 빠진 응답은 허용하지 않습니다.
    "required": ["title_candidates", "body", "tags"],
    # 프로그램이 모르는 추가 필드가 생기지 않게 합니다.
    "additionalProperties": False,
}
