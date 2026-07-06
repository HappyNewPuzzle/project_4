"""로컬 Ollama Vision 모델과 통신하는 클라이언트입니다.

추가 Python 패키지 없이 표준 라이브러리만 사용하며, 사진과 프롬프트는
기본적으로 사용자 PC의 Ollama 서버로만 전송됩니다.
"""

from __future__ import annotations

# Ollama REST API가 요구하는 Base64 문자열로 사진을 변환합니다.
import base64
# 요청과 응답의 JSON 데이터를 변환합니다.
import json
# HTTP 오류와 연결 오류를 구분해 처리합니다.
from urllib.error import HTTPError, URLError
# 로컬 Ollama 서버에 POST 요청을 보냅니다.
from urllib.request import Request, urlopen
# 사진 파일 경로를 안전하게 다룹니다.
from pathlib import Path
# Ollama 응답 딕셔너리의 여러 자료형을 표현합니다.
from typing import Any

# OpenAI 모드와 동일한 출력 구조를 Ollama에도 적용합니다.
from output_schema import BLOG_POST_SCHEMA


class OllamaClientError(Exception):
    """Ollama 연결, 모델 실행 또는 응답 처리에 실패했을 때 발생합니다."""


class BlogOllamaClient:
    """로컬 Ollama의 `/api/chat`을 이용해 사진 리뷰 글을 생성합니다."""

    def __init__(self, base_url: str, model: str, num_ctx: int = 32_768) -> None:
        # 주소 끝의 슬래시를 제거해 API 경로의 이중 슬래시를 방지합니다.
        self.base_url = base_url.rstrip("/")
        # .env에서 선택한 Vision 모델 이름을 저장합니다.
        self.model = model
        # 다중 사진의 시각 토큰까지 담을 Ollama 문맥 크기를 저장합니다.
        self.num_ctx = num_ctx

    @staticmethod
    def _encode_image(path: Path) -> str:
        """사진 하나를 Ollama REST API용 Base64 문자열로 변환합니다."""

        try:
            # 사진의 원본 바이트를 읽고 JSON에 담을 수 있는 ASCII 문자열로 바꿉니다.
            return base64.b64encode(path.read_bytes()).decode("ascii")
        except OSError as exc:
            # 어느 사진에서 오류가 났는지 전체 경로와 함께 안내합니다.
            raise OllamaClientError(f"사진을 읽을 수 없습니다 ({path}): {exc}") from exc

    @staticmethod
    def _parse_structured_content(content: str) -> dict[str, Any]:
        """Ollama 응답에서 JSON 객체를 추출하고 앞뒤 설명이나 코드펜스를 제거합니다."""

        # 모델이 JSON을 Markdown 코드 블록으로 감싼 경우 바깥 표시를 제거합니다.
        cleaned = content.strip()
        if cleaned.startswith("```"):
            # 첫 줄의 ```json 또는 ``` 표시를 버립니다.
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1 :]
            # 마지막 코드 블록 닫기 표시도 제거합니다.
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()

        try:
            # 가장 이상적인 경우에는 전체 문자열을 JSON으로 바로 해석합니다.
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # 앞뒤에 설명이 섞였다면 첫 `{`부터 마지막 `}`까지만 다시 시도합니다.
            object_start = cleaned.find("{")
            object_end = cleaned.rfind("}")
            if object_start == -1 or object_end <= object_start:
                raise
            result = json.loads(cleaned[object_start : object_end + 1])

        # 구조화 출력의 최상위 값은 반드시 딕셔너리여야 합니다.
        if not isinstance(result, dict):
            raise json.JSONDecodeError(
                "최상위 JSON 값이 객체가 아닙니다.",
                cleaned,
                0,
            )
        return result

    def _send_chat_request(self, request_body: dict[str, Any]) -> dict[str, Any]:
        """Ollama 채팅 요청 한 번을 보내고 서버의 JSON 응답을 반환합니다."""

        # 한글을 보존한 JSON 바이트를 만듭니다.
        encoded_body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
        # 로컬 Ollama 채팅 API에 보낼 HTTP 요청 객체를 구성합니다.
        request = Request(
            f"{self.base_url}/api/chat",
            data=encoded_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            # 사진이 많으면 오래 걸릴 수 있어 제한 시간을 10분으로 둡니다.
            with urlopen(request, timeout=600) as response:
                # HTTP 응답의 UTF-8 JSON을 파이썬 딕셔너리로 변환합니다.
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # 모델 미설치 등의 상세 메시지가 있으면 응답 본문에서 가져옵니다.
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaClientError(
                f"Ollama 요청에 실패했습니다 (HTTP {exc.code}): {detail}"
            ) from exc
        except URLError as exc:
            # 서버가 꺼져 있을 때 실행 방법을 함께 안내합니다.
            raise OllamaClientError(
                "Ollama 서버에 연결할 수 없습니다. Ollama를 실행한 뒤 다시 시도해주세요. "
                f"({exc.reason})"
            ) from exc
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            # 시간 초과와 깨진 서버 응답을 하나의 이해하기 쉬운 오류로 바꿉니다.
            raise OllamaClientError(f"Ollama 응답 처리에 실패했습니다: {exc}") from exc

        # 최상위 서버 응답이 객체가 아니면 message를 읽기 전에 중단합니다.
        if not isinstance(payload, dict):
            raise OllamaClientError("Ollama 서버 응답 형식이 올바르지 않습니다.")
        return payload

    def generate_post(
        self, instructions: str, user_prompt: str, image_paths: list[Path]
    ) -> dict[str, Any]:
        """프롬프트와 사진을 Ollama에 보내 구조화된 글을 반환합니다."""

        # REST API는 SDK와 달리 사진을 Base64 문자열 배열로 받습니다.
        images = [self._encode_image(path) for path in image_paths]
        # 시스템 규칙과 사용자 정보를 역할별 메시지로 나눠 요청합니다.
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": images,
                },
            ],
            # 한 번에 완성된 JSON 응답을 받도록 스트리밍을 끕니다.
            "stream": False,
            # OpenAI 모드와 같은 제목·본문·태그 구조를 강제합니다.
            "format": BLOG_POST_SCHEMA,
            # 작은 로컬 모델의 형식 위반과 근거 없는 창작을 줄이기 위해 0으로 둡니다.
            "options": {
                "temperature": 0,
                # 여러 사진과 긴 한국어 글이 잘리지 않도록 컨텍스트를 넉넉히 둡니다.
                "num_ctx": self.num_ctx,
                # 제목·본문·태그 JSON을 완성할 충분한 출력 토큰을 허용합니다.
                "num_predict": 4_096,
            },
        }

        # 첫 응답이 JSON 형식을 어기면 지침을 강화해 한 번 자동 재시도합니다.
        last_content = ""
        last_error: json.JSONDecodeError | None = None
        for attempt in range(2):
            if attempt == 1:
                # 두 번째 요청에서는 모델에 JSON 외의 문자를 절대 출력하지 않게 강조합니다.
                request_body["messages"][1]["content"] = (
                    f"{user_prompt}\n\n"
                    "이전 응답은 JSON 형식이 올바르지 않았습니다. "
                    "반드시 지정된 JSON Schema에 맞는 JSON 객체만 출력하세요. "
                    "코드 블록과 앞뒤 설명은 쓰지 마세요."
                )
            # 현재 조건으로 Ollama 채팅 요청을 보냅니다.
            payload = self._send_chat_request(request_body)
            # 정상 서버 응답은 message.content 안에 모델 생성 문자열을 담습니다.
            content = payload.get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise OllamaClientError(
                    "Ollama가 비어 있거나 올바르지 않은 응답을 반환했습니다."
                )
            last_content = content
            try:
                # 코드펜스와 불필요한 설명을 정리해 JSON 딕셔너리로 변환합니다.
                return self._parse_structured_content(content)
            except json.JSONDecodeError as exc:
                last_error = exc
                # 첫 실패는 자동으로 재요청하고 두 번째 실패 후에만 사용자에게 알립니다.
                continue

        # 개인정보 노출을 줄이면서 형식 문제를 찾을 수 있도록 앞부분만 표시합니다.
        preview = " ".join(last_content[:300].splitlines())
        raise OllamaClientError(
            "Ollama의 글 응답을 두 번 모두 JSON으로 해석할 수 없습니다. "
            f"응답 시작 부분: {preview}"
        ) from last_error
