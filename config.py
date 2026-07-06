"""환경 변수와 사용자 설정을 읽는 모듈입니다.

설정 처리 코드를 한곳에 모아 다른 파일이 환경 변수나 경로의 세부사항을
몰라도 되게 합니다.
"""

from __future__ import annotations

# settings.json의 JSON 문자열을 파이썬 객체로 변환합니다.
import json
# 운영체제 환경 변수에서 OpenAI 설정값을 가져옵니다.
import os
# 관련 설정값을 하나의 읽기 쉬운 객체로 묶습니다.
from dataclasses import dataclass
# 운영체제에 맞는 파일 경로를 안전하게 처리합니다.
from pathlib import Path
# JSON을 읽은 직후 아직 자료형이 정해지지 않은 값을 표현합니다.
from typing import Any

# 프로젝트의 .env 내용을 환경 변수처럼 읽을 수 있게 합니다.
from dotenv import load_dotenv


# 이 파일의 위치를 기준으로 삼아 어느 폴더에서 실행해도 경로가 유지되게 합니다.
BASE_DIR = Path(__file__).resolve().parent
# 음식점용과 상품용 프롬프트가 들어 있는 폴더입니다.
PROMPTS_DIR = BASE_DIR / "prompts"
# 개인 블로그 문체가 저장된 JSON 파일입니다.
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"
# 완성된 리뷰 TXT 파일을 저장할 폴더입니다.
OUTPUT_DIR = BASE_DIR / "outputs" / "generated_posts"
# ChatGPT에 붙여넣을 프롬프트 TXT 파일을 저장할 폴더입니다.
PROMPT_OUTPUT_DIR = BASE_DIR / "outputs" / "generated_prompts"
# 네이버 로그인 상태를 보관할 자동화 전용 Chrome 프로필 폴더입니다.
NAVER_BROWSER_PROFILE_DIR = BASE_DIR / "data" / "naver_browser_profile"


class ConfigError(Exception):
    """설정이 없거나 올바르지 않을 때 발생합니다."""


@dataclass(frozen=True)
class AppConfig:
    """프로그램 전체에서 사용하는 설정을 읽기 전용으로 묶습니다."""

    # OpenAI API 인증용 Key이며 수동·Ollama 모드에서는 없어도 됩니다.
    openai_api_key: str | None
    # OpenAI API 모드에서 사용할 Vision 모델 이름입니다.
    openai_model: str
    # Ollama 로컬 모드에서 사용할 Vision 모델 이름입니다.
    ollama_model: str
    # 로컬 Ollama REST API의 기본 주소입니다.
    ollama_base_url: str
    # 사진과 글을 한 요청에 담을 Ollama 문맥 크기입니다.
    ollama_num_ctx: int
    # 네이버 블로그 글쓰기 화면을 여는 주소입니다.
    naver_write_url: str
    # settings.json에서 읽은 말투와 고정 문구입니다.
    settings: dict[str, str]


def _load_settings() -> dict[str, str]:
    """settings.json을 읽고 필수 스타일 항목을 검사합니다."""

    try:
        # 한글과 이모티콘이 깨지지 않도록 UTF-8로 파일을 엽니다.
        with SETTINGS_PATH.open("r", encoding="utf-8") as file:
            # JSON 내용을 파이썬 객체로 변환합니다.
            data: Any = json.load(file)
    except FileNotFoundError as exc:
        # 설정 파일이 없으면 사용자가 확인할 정확한 경로를 알려줍니다.
        raise ConfigError(f"설정 파일을 찾을 수 없습니다: {SETTINGS_PATH}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        # 권한 문제와 JSON 문법 오류를 이해하기 쉬운 설정 오류로 바꿉니다.
        raise ConfigError(f"설정 파일을 읽을 수 없습니다: {exc}") from exc

    # 설정 최상위 값은 반드시 키와 값으로 구성된 객체여야 합니다.
    if not isinstance(data, dict):
        raise ConfigError("settings.json의 최상위 값은 JSON 객체여야 합니다.")

    # 글을 만들 때 반드시 필요한 스타일 항목 목록입니다.
    required_keys = {"tone", "emoji_style", "opening", "closing", "link_text"}
    # 필수 목록과 실제 키를 비교해 빠진 항목을 찾습니다.
    missing = required_keys - data.keys()
    if missing:
        # 누락된 항목을 정렬해 사용자가 한 번에 수정할 수 있게 안내합니다.
        raise ConfigError(
            "settings.json에 필요한 항목이 없습니다: " + ", ".join(sorted(missing))
        )

    # 프롬프트에 안전하게 넣도록 모든 설정값을 문자열로 통일합니다.
    return {key: str(value) for key, value in data.items()}


def load_config(require_openai_key: bool = False) -> AppConfig:
    """`.env`와 settings.json을 읽고 선택 모드에 필요한 설정을 반환합니다."""

    # 프로젝트 폴더에 있는 .env 파일만 명시적으로 불러옵니다.
    load_dotenv(BASE_DIR / ".env")
    # Key 양끝에 실수로 들어간 공백을 제거합니다.
    api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    if require_openai_key and not api_key:
        # Key가 없으면 유료 요청을 시도하기 전에 해결 방법을 안내합니다.
        raise ConfigError(
            "OPENAI_API_KEY가 없습니다. .env.example을 복사해 .env를 만들고 "
            "API Key를 입력해주세요."
        )

    # 모델을 지정하지 않았을 때 사용할 기본 Vision 모델을 설정합니다.
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
    if not openai_model:
        # 환경 변수 이름만 있고 값이 비어 있는 경우도 오류로 처리합니다.
        raise ConfigError("OPENAI_MODEL 값이 비어 있습니다.")

    # Ollama Vision 모델은 설치 안내가 쉬운 gemma3:4b를 기본값으로 사용합니다.
    ollama_model = os.getenv("OLLAMA_MODEL", "gemma3:4b").strip()
    if not ollama_model:
        raise ConfigError("OLLAMA_MODEL 값이 비어 있습니다.")

    # 다른 PC나 포트를 사용할 수 있도록 서버 주소도 환경 변수로 분리합니다.
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    if not ollama_base_url:
        raise ConfigError("OLLAMA_BASE_URL 값이 비어 있습니다.")

    # 다중 사진이 16K 문맥을 넘을 수 있어 기본 문맥 크기를 32K로 설정합니다.
    ollama_num_ctx_text = os.getenv("OLLAMA_NUM_CTX", "32768").strip()
    try:
        # 환경 변수의 문자열을 Ollama가 요구하는 정수로 변환합니다.
        ollama_num_ctx = int(ollama_num_ctx_text)
    except ValueError as exc:
        # 숫자가 아닌 값을 입력했을 때 정확한 설정 이름을 안내합니다.
        raise ConfigError("OLLAMA_NUM_CTX는 정수로 입력해주세요.") from exc
    if ollama_num_ctx < 8_192:
        # 사진 여러 장을 처리하기 어려운 지나치게 작은 설정은 미리 차단합니다.
        raise ConfigError("OLLAMA_NUM_CTX는 8192 이상으로 입력해주세요.")

    # 네이버가 로그인 사용자에게 제공하는 글쓰기 진입 주소를 설정합니다.
    naver_write_url = os.getenv(
        "NAVER_WRITE_URL",
        "https://blog.naver.com/GoBlogWrite.naver",
    ).strip()
    if not naver_write_url:
        raise ConfigError("NAVER_WRITE_URL 값이 비어 있습니다.")

    # 세 실행 모드에서 함께 사용할 설정 객체를 반환합니다.
    return AppConfig(
        openai_api_key=api_key,
        openai_model=openai_model,
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url,
        ollama_num_ctx=ollama_num_ctx,
        naver_write_url=naver_write_url,
        settings=_load_settings(),
    )
