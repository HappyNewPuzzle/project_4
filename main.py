"""개인용 네이버 블로그 작성 비서 콘솔 프로그램.

사용자와 대화하는 화면만 담당하며 설정, API, 글 생성은 전용 모듈에 맡깁니다.
"""

from __future__ import annotations

# 사용자가 입력한 Windows 사진 경로를 처리합니다.
from pathlib import Path

# ChatGPT용 프롬프트를 클립보드에 복사하는 기능입니다.
from clipboard_utils import ClipboardError, copy_to_clipboard
# 환경 변수와 블로그 스타일을 읽는 기능입니다.
from config import ConfigError, load_config
# 로컬 Ollama Vision 모델 클라이언트와 통신 오류입니다.
from ollama_client import BlogOllamaClient, OllamaClientError
# OpenAI API 클라이언트와 통신 오류입니다.
from openai_client import BlogOpenAIClient, OpenAIClientError
# 입력, 생성, 출력, 저장에 필요한 핵심 기능입니다.
from post_generator import (
    InputError,
    ReviewInput,
    SaveError,
    build_chatgpt_prompt,
    format_post,
    generate_post,
    save_chatgpt_prompt,
    save_post,
)


def choose_generation_mode() -> str:
    """ChatGPT 수동, Ollama 로컬, OpenAI API 중 실행 모드를 선택합니다."""

    # 각 모드의 비용과 동작 차이를 선택 화면에서 바로 설명합니다.
    print("\n글 생성 방식을 선택해주세요.")
    print("1. ChatGPT용 프롬프트 만들기 (Plus에서 직접 붙여넣기)")
    print("2. Ollama 로컬 모델로 글 생성 (API 요금 없음)")
    print("3. OpenAI API로 글 생성 (API 요금 별도)")
    # 사용자가 입력한 번호의 양끝 공백을 제거합니다.
    choice = input("선택 (1/2/3): ").strip()
    # 화면 번호를 프로그램 내부에서 사용할 모드 이름에 연결합니다.
    choices = {"1": "chatgpt", "2": "ollama", "3": "openai"}
    # 목록에 없는 값은 이후 입력을 받기 전에 거부합니다.
    if choice not in choices:
        raise InputError("1, 2, 3 중 하나를 입력해주세요.")
    # 선택된 내부 모드 이름을 반환합니다.
    return choices[choice]


def choose_review_type() -> str:
    """숫자로 받은 리뷰 종류를 내부 영문 코드로 변환합니다."""

    # 사용자에게 선택 가능한 리뷰 종류를 번호로 보여줍니다.
    print("\n리뷰 종류를 선택해주세요.")
    print("1. 음식점 리뷰")
    print("2. 상품 리뷰")
    # 입력값 양끝의 불필요한 공백을 제거합니다.
    choice = input("선택 (1/2): ").strip()
    # 화면 번호와 내부 리뷰 종류를 연결합니다.
    choices = {"1": "restaurant", "2": "product"}
    # 1과 2 이외의 입력은 API 실행 전에 거부합니다.
    if choice not in choices:
        raise InputError("1 또는 2를 입력해주세요.")
    # 선택한 번호에 해당하는 내부 코드를 반환합니다.
    return choices[choice]


def read_rating() -> float:
    """별점을 입력받아 소수점 사용이 가능한 숫자로 변환합니다."""

    # 문자열로 입력된 별점의 양끝 공백을 제거합니다.
    value = input("별점 (1~5, 소수 가능): ").strip()
    try:
        # `4.5` 같은 입력을 실제 실수 자료형으로 바꿉니다.
        return float(value)
    except ValueError as exc:
        # 숫자가 아닌 입력을 이해하기 쉬운 오류로 안내합니다.
        raise InputError("별점은 숫자로 입력해주세요.") from exc


def read_image_paths() -> list[Path]:
    """빈 줄이 입력될 때까지 사진 경로를 여러 개 받습니다."""

    # 사진을 여러 장 입력하고 끝내는 방법을 안내합니다.
    print("사진 파일 경로를 한 줄에 하나씩 입력해주세요.")
    print("입력을 마치려면 빈 줄에서 Enter를 누르세요.")
    # 입력된 경로를 순서대로 보관할 빈 목록입니다.
    paths: list[Path] = []
    # 사용자가 빈 줄을 입력할 때까지 계속 반복합니다.
    while True:
        # 탐색기의 '경로로 복사'가 붙이는 바깥 큰따옴표도 제거합니다.
        value = input(f"사진 {len(paths) + 1}: ").strip().strip('"')
        # 빈 줄을 사진 입력 완료 신호로 사용합니다.
        if not value:
            break
        # 홈 폴더 표현을 확장하고 절대 경로로 바꿔 저장합니다.
        paths.append(Path(value).expanduser().resolve())
    # 한 번에 수집한 모든 사진 경로를 반환합니다.
    return paths


def collect_input() -> ReviewInput:
    """리뷰 작성에 필요한 정보를 순서대로 모두 입력받습니다."""

    # 먼저 음식점과 상품 중 사용할 템플릿을 결정합니다.
    review_type = choose_review_type()
    # 선택한 종류에 맞게 이름 입력 문구를 바꿉니다.
    label = "음식점명" if review_type == "restaurant" else "상품명"
    # 개별 입력값들을 하나의 ReviewInput 객체로 묶어 반환합니다.
    return ReviewInput(
        review_type=review_type,
        name=input(f"{label}: ").strip(),
        link=input("링크: ").strip(),
        memo=input("한줄 메모: ").strip(),
        rating=read_rating(),
        image_paths=read_image_paths(),
    )


def run() -> int:
    """전체 실행 순서를 관리하고 운영체제 종료 코드를 반환합니다."""

    # 프로그램이 시작됐음을 알아보기 쉬운 제목으로 표시합니다.
    print("=" * 50)
    print("  개인용 네이버 블로그 작성 비서")
    print("=" * 50)

    try:
        # API 사용 여부를 먼저 정해 불필요한 API Key 요구를 피합니다.
        mode = choose_generation_mode()
        # OpenAI 모드에서만 API Key를 필수로 검사합니다.
        config = load_config(require_openai_key=(mode == "openai"))
        # 리뷰 정보와 사진 경로를 콘솔에서 수집합니다.
        review = collect_input()

        # ChatGPT 수동 모드는 API를 호출하지 않고 붙여넣을 프롬프트만 만듭니다.
        if mode == "chatgpt":
            # 템플릿과 사용자 정보를 합친 완성 프롬프트를 만듭니다.
            prompt = build_chatgpt_prompt(review, config.settings)
            # 첨부할 사진 목록과 프롬프트를 나중에도 볼 수 있게 저장합니다.
            output_path = save_chatgpt_prompt(prompt, review)

            try:
                # ChatGPT 대화창에서 바로 붙여넣을 수 있도록 자동 복사합니다.
                copy_to_clipboard(prompt)
                clipboard_message = "프롬프트를 클립보드에 복사했습니다."
            except ClipboardError as exc:
                # 복사가 실패해도 저장 파일과 콘솔 결과는 계속 사용할 수 있습니다.
                clipboard_message = f"자동 복사는 실패했습니다: {exc}"

            # 사용자가 직접 선택해 복사할 수도 있도록 콘솔에도 프롬프트를 표시합니다.
            print("\n=== ChatGPT에 붙여넣을 프롬프트 ===")
            print(prompt)
            print(f"\n{clipboard_message}")
            print(f"저장 완료: {output_path}")
            print("사진을 ChatGPT에 먼저 첨부한 뒤 프롬프트를 붙여넣어주세요.")
            return 0

        # Ollama 모드는 API Key 없이 로컬 REST API 클라이언트를 만듭니다.
        if mode == "ollama":
            client = BlogOllamaClient(
                base_url=config.ollama_base_url,
                model=config.ollama_model,
            )
            selected_model = config.ollama_model
            provider_name = "Ollama"
        else:
            # OpenAI 모드에서는 설정 단계에서 Key 존재가 이미 확인됐습니다.
            assert config.openai_api_key is not None
            client = BlogOpenAIClient(
                config.openai_api_key,
                config.openai_model,
            )
            selected_model = config.openai_model
            provider_name = "OpenAI API"

        # 모델 실행 중임을 사용자가 알 수 있게 표시합니다.
        print(
            f"\n사진을 분석하고 글을 생성하는 중입니다... "
            f"({provider_name}: {selected_model})"
        )
        # 입력과 사진을 이용해 구조화된 리뷰 글을 생성합니다.
        post = generate_post(review, config.settings, client)
        # 생성에 성공한 결과를 TXT 파일로 저장합니다.
        output_path = save_post(post, review.name)

        # 같은 결과를 콘솔에도 출력해 즉시 복사할 수 있게 합니다.
        print("\n" + format_post(post))
        # 나중에 파일을 찾을 수 있도록 전체 저장 경로를 보여줍니다.
        print(f"저장 완료: {output_path}")
        # 정상 종료를 뜻하는 코드 0을 반환합니다.
        return 0
    except (
        ConfigError,
        InputError,
        OllamaClientError,
        OpenAIClientError,
        SaveError,
    ) as exc:
        # 예상 가능한 오류는 복잡한 추적 정보 없이 메시지만 표시합니다.
        print(f"\n[오류] {exc}")
        return 1
    except KeyboardInterrupt:
        # Ctrl+C 취소도 긴 오류 화면 없이 안전하게 처리합니다.
        print("\n\n사용자가 실행을 취소했습니다.")
        return 130
    except Exception as exc:
        # 미처 예상하지 못한 오류도 프로그램이 그대로 무너지지 않게 처리합니다.
        print(f"\n[예상하지 못한 오류] {exc}")
        return 1


# 이 파일을 직접 실행할 때만 프로그램을 시작합니다.
if __name__ == "__main__":
    # run의 반환값을 실제 프로세스 종료 코드로 전달합니다.
    raise SystemExit(run())
