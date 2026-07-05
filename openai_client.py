"""OpenAI Responses API 호출과 이미지 인코딩을 담당합니다.

API 통신 세부사항을 이 파일에 모아 나머지 코드가 간단하게 유지되도록 합니다.
"""

from __future__ import annotations

# 사진 바이트를 API 전송용 문자열로 변환합니다.
import base64
# 모델의 JSON 문자열 응답을 파이썬 객체로 변환합니다.
import json
# 확장자를 보고 JPEG, PNG 같은 이미지 MIME 타입을 찾습니다.
import mimetypes
# 로컬 사진 경로를 안전하게 처리합니다.
from pathlib import Path
# 여러 자료형이 들어갈 API 딕셔너리를 표현합니다.
from typing import Any

# 공식 OpenAI Python SDK의 클라이언트를 사용합니다.
from openai import OpenAI


class OpenAIClientError(Exception):
    """OpenAI 요청 또는 응답 처리에 실패했을 때 발생합니다."""


# 모델이 반드시 지켜야 하는 최종 응답 구조를 정의합니다.
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


class BlogOpenAIClient:
    """이미지와 프롬프트를 모델에 전달하는 작은 API 래퍼입니다."""

    def __init__(self, api_key: str, model: str) -> None:
        # 요청은 120초 후 중단하고 일시적인 실패는 최대 두 번 재시도합니다.
        self.client = OpenAI(api_key=api_key, timeout=120.0, max_retries=2)
        # .env에서 선택된 모델 이름을 각 요청에 재사용합니다.
        self.model = model

    @staticmethod
    def _image_to_data_url(path: Path) -> str:
        """로컬 사진 하나를 Responses API용 data URL로 바꿉니다."""

        # 확장자를 보고 image/jpeg 같은 MIME 타입을 추측합니다.
        mime_type, _ = mimetypes.guess_type(path.name)
        # 알 수 없는 확장자일 때 사용할 안전한 기본값입니다.
        mime_type = mime_type or "application/octet-stream"

        try:
            # 사진을 읽고 API 요청 JSON에 넣을 수 있는 Base64 문자열로 바꿉니다.
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except OSError as exc:
            # 어떤 사진을 읽지 못했는지 경로와 함께 알려줍니다.
            raise OpenAIClientError(f"사진을 읽을 수 없습니다 ({path}): {exc}") from exc

        # 이미지 형식과 Base64 내용을 하나의 data URL로 결합합니다.
        return f"data:{mime_type};base64,{encoded}"

    def generate_post(
        self, instructions: str, user_prompt: str, image_paths: list[Path]
    ) -> dict[str, Any]:
        """프롬프트와 모든 사진을 전송하고 구조화된 결과를 반환합니다."""

        # content의 첫 항목에는 사용자가 입력한 리뷰 정보를 넣습니다.
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": user_prompt}
        ]
        # 입력된 사진을 순서대로 이미지 항목에 추가합니다.
        content.extend(
            {
                "type": "input_image",
                "image_url": self._image_to_data_url(path),
                # 리뷰에는 저해상도 분석으로 충분하므로 비용을 줄이는 low를 사용합니다.
                "detail": "low",
            }
            for path in image_paths
        )

        try:
            # 텍스트와 사진을 Responses API에 한 번에 전달합니다.
            response = self.client.responses.create(
                model=self.model,
                # 반복되는 글쓰기 규칙과 개인 스타일을 시스템 지침으로 보냅니다.
                instructions=instructions,
                # 매번 달라지는 리뷰 정보와 사진을 사용자 입력으로 보냅니다.
                input=[{"role": "user", "content": content}],
                # 개인 사진과 결과가 API 응답 저장소에 보관되지 않게 합니다.
                store=False,
                text={
                    "format": {
                        # 자유 형식 대신 위 스키마를 따르는 JSON 응답을 요구합니다.
                        "type": "json_schema",
                        "name": "blog_review_post",
                        "strict": True,
                        "schema": BLOG_POST_SCHEMA,
                    }
                },
            )
        except Exception as exc:
            # 인증, 한도, 네트워크 등 SDK 오류를 프로그램 전용 오류로 통일합니다.
            raise OpenAIClientError(f"OpenAI API 호출에 실패했습니다: {exc}") from exc

        # 정상 응답이라도 텍스트가 없으면 후속 처리를 중단합니다.
        if not response.output_text:
            raise OpenAIClientError("OpenAI가 비어 있는 응답을 반환했습니다.")

        try:
            # 모델이 반환한 JSON 문자열을 파이썬 딕셔너리로 해석합니다.
            result = json.loads(response.output_text)
        except json.JSONDecodeError as exc:
            # 예상과 달리 JSON이 깨져도 프로그램이 그대로 종료되지 않게 합니다.
            raise OpenAIClientError("OpenAI 응답을 JSON으로 해석할 수 없습니다.") from exc

        # 최상위 응답이 딕셔너리인지 애플리케이션에서도 한 번 더 확인합니다.
        if not isinstance(result, dict):
            raise OpenAIClientError("OpenAI 응답 형식이 올바르지 않습니다.")
        # 검증된 결과를 글 생성 모듈에 반환합니다.
        return result
