"""개인용 네이버 블로그 작성 비서 콘솔 프로그램.

사용자와 대화하는 화면만 담당하며 설정, API, 글 생성은 전용 모듈에 맡깁니다.
"""

from __future__ import annotations

# 사용자가 입력한 Windows 사진 경로를 처리합니다.
from pathlib import Path

# 환경 변수와 블로그 스타일을 읽는 기능입니다.
from config import ConfigError, load_config
# OpenAI API 클라이언트와 통신 오류입니다.
from openai_client import BlogOpenAIClient, OpenAIClientError
# 입력, 생성, 출력, 저장에 필요한 핵심 기능입니다.
from post_generator import (
    InputError,
    ReviewInput,
    SaveError,
    format_post,
    generate_post,
    save_post,
)


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
        # API Key, 모델, 개인 스타일 설정을 먼저 읽습니다.
        config = load_config()
        # 리뷰 정보와 사진 경로를 콘솔에서 수집합니다.
        review = collect_input()
        # 읽은 API Key와 모델로 OpenAI 클라이언트를 만듭니다.
        client = BlogOpenAIClient(config.api_key, config.model)

        # 네트워크 처리 중임을 사용자가 알 수 있게 표시합니다.
        print(f"\n사진을 분석하고 글을 생성하는 중입니다... ({config.model})")
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
    except (ConfigError, InputError, OpenAIClientError, SaveError) as exc:
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
