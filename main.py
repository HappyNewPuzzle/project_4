"""개인용 네이버 블로그 작성 비서 콘솔 프로그램.

사용자와 대화하는 화면만 담당하며 설정, API, 글 생성은 전용 모듈에 맡깁니다.
"""

from __future__ import annotations

# 사용자가 입력한 Windows 사진 경로를 처리합니다.
from pathlib import Path
# 파일명 속 숫자를 실제 숫자 순서로 정렬하기 위해 사용합니다.
import re

# ChatGPT용 프롬프트를 클립보드에 복사하는 기능입니다.
from clipboard_utils import ClipboardError, copy_to_clipboard
# 환경 변수와 블로그 스타일을 읽는 기능입니다.
from config import ConfigError, NAVER_BROWSER_PROFILE_DIR, load_config
# 네이버 스마트에디터 반자동 배치 기능과 전용 오류입니다.
from naver_automation import NaverAutomationError, NaverBlogAutomator
# 로컬 Ollama Vision 모델 클라이언트와 통신 오류입니다.
from ollama_client import BlogOllamaClient, OllamaClientError
# OpenAI API 클라이언트와 통신 오류입니다.
from openai_client import BlogOpenAIClient, OpenAIClientError
# 입력, 생성, 출력, 저장에 필요한 핵심 기능입니다.
from post_generator import (
    InputError,
    ReviewInput,
    SaveError,
    SUPPORTED_IMAGE_EXTENSIONS,
    build_chatgpt_prompt,
    format_post,
    generate_post,
    save_chatgpt_prompt,
    save_post,
)


def choose_generation_mode() -> str:
    """ChatGPT 수동, Ollama 로컬, OpenAI API 중 실행 모드를 선택합니다."""

    # 화면 번호를 프로그램 내부에서 사용할 모드 이름에 연결합니다.
    choices = {"1": "chatgpt", "2": "ollama", "3": "openai"}
    # 올바른 번호를 입력할 때까지 같은 선택 화면을 반복합니다.
    while True:
        # 각 모드의 비용과 동작 차이를 선택 화면에서 바로 설명합니다.
        print("\n글 생성 방식을 선택해주세요.")
        print("1. ChatGPT용 프롬프트 만들기 (Plus에서 직접 붙여넣기)")
        print("2. Ollama 로컬 모델로 글 생성 (API 요금 없음)")
        print("3. OpenAI API로 글 생성 (API 요금 별도)")
        # 사용자가 입력한 번호의 양끝 공백을 제거합니다.
        choice = input("선택 (1/2/3): ").strip()
        # 올바른 번호라면 선택된 내부 모드 이름을 반환합니다.
        if choice in choices:
            return choices[choice]
        # 잘못된 값은 프로그램을 끝내지 않고 다시 안내합니다.
        print("[안내] 1, 2, 3 중 하나를 입력해주세요.")


def ask_yes_no(message: str) -> bool:
    """사용자에게 예/아니요를 입력받아 True 또는 False로 반환합니다."""

    # 잘못 입력해도 생성한 글을 버리지 않고 같은 질문을 다시 표시합니다.
    while True:
        # 대소문자와 한글·영문 입력을 모두 허용합니다.
        choice = input(f"{message} (y/n): ").strip().lower()
        # 한글 키보드 상태에서 영문 y/n 키를 누른 결과도 자동으로 변환합니다.
        if choice == "ㅛ":
            choice = "y"
        elif choice == "ㅜ":
            choice = "n"
        # 긍정 표현이면 True를 반환합니다.
        if choice in {"y", "yes", "예", "네"}:
            return True
        # 부정 표현이면 False를 반환합니다.
        if choice in {"n", "no", "아니오", "아니요"}:
            return False
        # 그 외 입력은 프로그램을 종료하지 않고 다시 안내합니다.
        print("[안내] y 또는 n으로 입력해주세요.")


def choose_title(title_candidates: list[str]) -> str:
    """네이버 편집기에 넣을 제목을 다섯 후보 중에서 선택합니다."""

    # 잘못 입력해도 글 생성부터 다시 하지 않도록 선택이 끝날 때까지 반복합니다.
    while True:
        # 이미 출력된 제목을 선택 화면에서도 다시 보여줍니다.
        print("\n네이버 블로그에 사용할 제목을 선택해주세요.")
        for index, title in enumerate(title_candidates, 1):
            print(f"{index}. {title}")
        # 문자열 입력을 숫자로 바꿉니다.
        try:
            choice = int(input(f"제목 번호 (1~{len(title_candidates)}): ").strip())
        except ValueError:
            print("[안내] 제목 번호는 숫자로 입력해주세요.")
            continue
        # 올바른 범위라면 목록 인덱스로 변환해 제목을 반환합니다.
        if 1 <= choice <= len(title_candidates):
            return title_candidates[choice - 1]
        print(f"[안내] 1부터 {len(title_candidates)} 사이의 번호를 입력해주세요.")


def choose_review_type() -> str:
    """숫자로 받은 리뷰 종류를 내부 영문 코드로 변환합니다."""

    # 화면 번호와 내부 리뷰 종류를 연결합니다.
    choices = {"1": "restaurant", "2": "product"}
    # 올바른 리뷰 번호를 받을 때까지 같은 질문을 반복합니다.
    while True:
        # 사용자에게 선택 가능한 리뷰 종류를 번호로 보여줍니다.
        print("\n리뷰 종류를 선택해주세요.")
        print("1. 음식점 리뷰")
        print("2. 상품 리뷰")
        # 입력값 양끝의 불필요한 공백을 제거합니다.
        choice = input("선택 (1/2): ").strip()
        # 올바른 번호라면 해당 내부 코드를 반환합니다.
        if choice in choices:
            return choices[choice]
        # 잘못된 문자나 번호는 종료하지 않고 다시 입력받습니다.
        print("[안내] 1 또는 2를 입력해주세요.")


def read_rating() -> float:
    """별점을 입력받아 소수점 사용이 가능한 숫자로 변환합니다."""

    # 숫자이면서 1~5 범위인 별점이 들어올 때까지 반복합니다.
    while True:
        # 문자열로 입력된 별점의 양끝 공백을 제거합니다.
        value = input("별점 (1~5, 소수 가능): ").strip()
        try:
            # `4.5` 같은 입력을 실제 실수 자료형으로 바꿉니다.
            rating = float(value)
        except ValueError:
            # 숫자가 아닌 입력은 프로그램을 종료하지 않고 다시 묻습니다.
            print("[안내] 별점은 숫자로 입력해주세요.")
            continue
        # 정상 범위라면 검증된 별점을 반환합니다.
        if 1 <= rating <= 5:
            return rating
        print("[안내] 별점은 1점부터 5점 사이로 입력해주세요.")


def read_required_text(label: str) -> str:
    """공백이 아닌 필수 문자열을 입력할 때까지 같은 항목을 반복합니다."""

    while True:
        # 화면에 표시할 항목명을 받아 사용자 입력의 양끝 공백을 제거합니다.
        value = input(f"{label}: ").strip()
        # 한 글자라도 입력됐다면 정상 값으로 반환합니다.
        if value:
            return value
        # 빈 값은 프로그램을 끝내지 않고 해당 항목만 다시 묻습니다.
        print(f"[안내] {label} 항목을 입력해주세요.")


def read_image_paths() -> list[Path]:
    """사진 파일이나 폴더 경로를 받아 지원 이미지를 한꺼번에 수집합니다."""

    # 개별 파일뿐 아니라 사진이 모인 폴더도 한 번에 입력할 수 있다고 안내합니다.
    print("사진 파일 또는 사진 폴더 경로를 입력해주세요.")
    print("폴더를 입력하면 내부의 지원 이미지를 파일명 순서로 모두 추가합니다.")
    print("입력을 마치려면 빈 줄에서 Enter를 누르세요.")
    # 입력된 경로를 순서대로 보관할 빈 목록입니다.
    paths: list[Path] = []
    # 사용자가 빈 줄을 입력할 때까지 계속 반복합니다.
    while True:
        # 탐색기의 '경로로 복사'가 붙이는 바깥 큰따옴표도 제거합니다.
        value = input(f"사진/폴더 {len(paths) + 1}: ").strip().strip('"')
        # 빈 줄을 사진 입력 완료 신호로 사용합니다.
        if not value:
            # 사진을 한 장도 넣지 않았다면 종료하지 않고 첫 사진부터 다시 받습니다.
            if not paths:
                print("[안내] 사진 경로를 한 개 이상 입력해주세요.")
                continue
            break
        # 홈 폴더 표현을 확장하고 절대 경로로 바꿔 저장합니다.
        path = Path(value).expanduser().resolve()
        # 존재하지 않는 경로는 목록에 넣지 않고 같은 번호를 다시 묻습니다.
        if not path.exists():
            print(f"[안내] 파일 또는 폴더를 찾을 수 없습니다: {path}")
            continue
        # 폴더가 입력되면 바로 아래에 있는 지원 이미지들을 자연스러운 순서로 찾습니다.
        if path.is_dir():
            folder_images = sorted(
                (
                    item.resolve()
                    for item in path.iterdir()
                    if item.is_file()
                    and item.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
                ),
                key=_natural_path_sort_key,
            )
            # 지원 이미지가 없는 폴더는 이유를 안내하고 다른 경로를 받습니다.
            if not folder_images:
                print(f"[안내] 폴더에 지원되는 사진이 없습니다: {path}")
                continue
            # 이미 개별 입력했거나 다른 폴더에서 추가된 같은 사진은 제외합니다.
            new_images = [item for item in folder_images if item not in paths]
            paths.extend(new_images)
            print(
                f"[안내] 폴더에서 사진 {len(new_images)}장을 추가했습니다. "
                f"(현재 총 {len(paths)}장)"
            )
            # 실제 업로드 순서를 사용자가 확인할 수 있도록 파일명을 보여줍니다.
            for index, image_path in enumerate(new_images, len(paths) - len(new_images) + 1):
                print(f"  {index}. {image_path.name}")
            continue
        # 폴더가 아니라면 일반 파일인지 다시 확인합니다.
        if not path.is_file():
            print(f"[안내] 일반 사진 파일이 아닙니다: {path}")
            continue
        # OpenAI와 Ollama가 지원하지 않는 확장자도 입력 단계에서 바로 안내합니다.
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
            print(f"[안내] 지원하지 않는 사진 형식입니다. 지원 형식: {allowed}")
            continue
        # 같은 사진을 두 번 입력한 경우에는 중복으로 업로드하지 않습니다.
        if path in paths:
            print(f"[안내] 이미 추가된 사진입니다: {path.name}")
            continue
        paths.append(path)
    # 한 번에 수집한 모든 사진 경로를 반환합니다.
    return paths


def _natural_path_sort_key(path: Path) -> list[tuple[int, int | str]]:
    """`사진2`가 `사진10`보다 먼저 오도록 숫자를 고려한 정렬 키를 만듭니다."""

    # 파일명을 숫자 부분과 일반 문자 부분으로 나눕니다.
    parts = re.split(r"(\d+)", path.name.casefold())
    # 숫자와 문자열을 직접 비교하지 않도록 종류 표시와 값을 튜플로 묶습니다.
    return [
        (0, int(part)) if part.isdigit() else (1, part)
        for part in parts
        if part
    ]


def collect_input() -> ReviewInput:
    """리뷰 작성에 필요한 정보를 순서대로 모두 입력받습니다."""

    # 먼저 음식점과 상품 중 사용할 템플릿을 결정합니다.
    review_type = choose_review_type()
    # 선택한 종류에 맞게 이름 입력 문구를 바꿉니다.
    label = "음식점명" if review_type == "restaurant" else "상품명"
    # 개별 입력값들을 하나의 ReviewInput 객체로 묶어 반환합니다.
    return ReviewInput(
        review_type=review_type,
        name=read_required_text(label),
        link=read_required_text("링크"),
        memo=read_required_text("한줄 메모"),
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

        # 생성 후 원할 때만 네이버 브라우저 자동화를 시작합니다.
        if ask_yes_no("\n네이버 글쓰기 화면에 사진과 본문을 자동 배치할까요?"):
            # 다섯 제목 중 실제 편집기에 사용할 하나를 선택합니다.
            selected_title = choose_title(post.title_candidates)
            # 발행 설정의 태그 입력란에서 바로 붙여넣도록 태그를 복사합니다.
            tag_text = " ".join(f"#{tag}" for tag in post.tags)
            try:
                copy_to_clipboard(tag_text)
                print("태그 10개를 클립보드에 복사했습니다.")
            except ClipboardError as exc:
                # 자동 복사가 실패해도 본문 배치는 계속 진행할 수 있습니다.
                print(f"[안내] 태그 자동 복사는 실패했습니다: {exc}")

            # 로그인 상태를 보존하는 전용 Chrome 프로필로 편집기를 엽니다.
            automator = NaverBlogAutomator(
                write_url=config.naver_write_url,
                profile_dir=NAVER_BROWSER_PROFILE_DIR,
            )
            # 제목, 사진, 본문만 채우고 발행은 사용자가 직접 결정합니다.
            automator.fill_draft(
                title=selected_title,
                body=post.body,
                image_paths=review.image_paths,
            )
        # 정상 종료를 뜻하는 코드 0을 반환합니다.
        return 0
    except (
        ConfigError,
        InputError,
        NaverAutomationError,
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
