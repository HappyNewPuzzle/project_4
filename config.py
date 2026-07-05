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


class ConfigError(Exception):
    """설정이 없거나 올바르지 않을 때 발생합니다."""


@dataclass(frozen=True)
class AppConfig:
    """프로그램 전체에서 사용하는 설정을 읽기 전용으로 묶습니다."""

    # OpenAI API 인증용 비밀 Key입니다.
    api_key: str
    # 사진 분석과 글 생성에 사용할 모델 이름입니다.
    model: str
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


def load_config() -> AppConfig:
    """`.env`와 `settings.json`을 읽어 실행 설정을 반환합니다."""

    # 프로젝트 폴더에 있는 .env 파일만 명시적으로 불러옵니다.
    load_dotenv(BASE_DIR / ".env")
    # Key 양끝에 실수로 들어간 공백을 제거합니다.
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        # Key가 없으면 유료 요청을 시도하기 전에 해결 방법을 안내합니다.
        raise ConfigError(
            "OPENAI_API_KEY가 없습니다. .env.example을 복사해 .env를 만들고 "
            "API Key를 입력해주세요."
        )

    # 모델을 지정하지 않았을 때 사용할 기본 Vision 모델을 설정합니다.
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
    if not model:
        # 환경 변수 이름만 있고 값이 비어 있는 경우도 오류로 처리합니다.
        raise ConfigError("OPENAI_MODEL 값이 비어 있습니다.")

    # 검증된 API 정보와 블로그 스타일을 하나의 설정 객체로 반환합니다.
    return AppConfig(api_key=api_key, model=model, settings=_load_settings())
