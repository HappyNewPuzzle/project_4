"""여러 네이버 계정의 Chrome 로그인 프로필을 만들고 선택합니다.

비밀번호는 저장하지 않으며, 계정별 브라우저 폴더에 로그인 쿠키만 분리해
보관합니다.
"""

from __future__ import annotations

# 프로필 폴더 이름에 사용할 수 없는 문자를 정리합니다.
import re
# 프로필 폴더 경로를 안전하게 다룹니다.
from pathlib import Path

# 기존 단일 프로필과 새 다중 프로필의 기본 위치를 가져옵니다.
from config import NAVER_BROWSER_PROFILE_DIR, NAVER_BROWSER_PROFILES_DIR


class NaverProfileError(Exception):
    """계정 프로필을 조회하거나 만들 수 없을 때 발생합니다."""


def _safe_profile_name(name: str) -> str:
    """사용자가 입력한 계정 별칭을 Windows 폴더에 안전한 이름으로 바꿉니다."""

    # Windows 금지 문자와 제어 문자를 밑줄로 바꿉니다.
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" ._")
    # 지나치게 긴 폴더 이름은 Chrome 내부 경로 제한 문제를 만들 수 있어 줄입니다.
    return safe_name[:50]


def discover_naver_profiles(
    profiles_dir: Path = NAVER_BROWSER_PROFILES_DIR,
    legacy_profile_dir: Path = NAVER_BROWSER_PROFILE_DIR,
) -> list[tuple[str, Path]]:
    """기존 기본 계정과 새로 만든 계정별 프로필을 화면 표시 순서로 반환합니다."""

    profiles: list[tuple[str, Path]] = []
    try:
        # 이전 버전에서 이미 로그인한 단일 프로필은 삭제하거나 이동하지 않고 재사용합니다.
        if legacy_profile_dir.exists() and any(legacy_profile_dir.iterdir()):
            profiles.append(("기존 기본 계정", legacy_profile_dir))
        # 새 방식의 하위 폴더 하나를 네이버 계정 프로필 하나로 취급합니다.
        if profiles_dir.exists():
            account_folders = sorted(
                (path for path in profiles_dir.iterdir() if path.is_dir()),
                key=lambda path: path.name.casefold(),
            )
            profiles.extend((path.name, path) for path in account_folders)
    except OSError as exc:
        raise NaverProfileError(f"네이버 계정 프로필을 조회하지 못했습니다: {exc}") from exc
    return profiles


def choose_naver_profile() -> Path:
    """저장된 계정 프로필을 선택하거나 새 계정용 프로필을 생성합니다."""

    while True:
        # 매 반복마다 목록을 다시 읽어 방금 만든 프로필도 즉시 반영합니다.
        profiles = discover_naver_profiles()
        print("\n네이버 계정 프로필을 선택해주세요.")
        for index, (label, _) in enumerate(profiles, 1):
            print(f"{index}. {label}")
        new_profile_number = len(profiles) + 1
        print(f"{new_profile_number}. 새 계정 추가")

        # 숫자가 아닌 값과 범위를 벗어난 번호는 종료하지 않고 다시 질문합니다.
        choice = input(f"선택 (1~{new_profile_number}): ").strip()
        try:
            selected_number = int(choice)
        except ValueError:
            print("[안내] 계정 프로필 번호를 숫자로 입력해주세요.")
            continue
        if not 1 <= selected_number <= new_profile_number:
            print(f"[안내] 1부터 {new_profile_number} 사이의 번호를 입력해주세요.")
            continue

        # 기존 프로필을 골랐다면 해당 계정의 로그인 상태 폴더를 바로 반환합니다.
        if selected_number <= len(profiles):
            label, profile_path = profiles[selected_number - 1]
            print(f"[안내] '{label}' 계정 프로필을 사용합니다.")
            return profile_path

        # 새 계정은 실제 네이버 ID 대신 사용자가 알아볼 별칭만 입력받습니다.
        profile_name = input("새 계정 별칭 (예: 개인블로그): ").strip()
        safe_name = _safe_profile_name(profile_name)
        if not safe_name:
            print("[안내] 계정 별칭을 입력해주세요.")
            continue
        profile_path = NAVER_BROWSER_PROFILES_DIR / safe_name
        if profile_path.exists():
            print("[안내] 같은 이름의 계정 프로필이 이미 있습니다. 목록에서 선택해주세요.")
            continue
        try:
            # 빈 Chrome 프로필을 만들고 실제 로그인은 열린 브라우저에서 사용자가 진행합니다.
            profile_path.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise NaverProfileError(
                f"새 네이버 계정 프로필을 만들지 못했습니다: {exc}"
            ) from exc
        print(
            f"[안내] '{safe_name}' 프로필을 만들었습니다. "
            "열리는 브라우저에서 해당 네이버 계정으로 로그인해주세요."
        )
        return profile_path
