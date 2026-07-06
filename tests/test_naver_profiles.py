"""네이버 계정별 Chrome 프로필 생성과 선택 기능을 검증합니다."""

from __future__ import annotations

# 테스트 폴더를 실행 후 자동으로 정리합니다.
import tempfile
# 표준 테스트 도구와 경로 기능을 사용합니다.
import unittest
from pathlib import Path
# 사용자 입력과 기본 프로필 경로를 테스트 값으로 교체합니다.
from unittest.mock import patch

# 검증할 프로필 모듈의 공개 기능을 가져옵니다.
import naver_profiles
from naver_profiles import choose_naver_profile, discover_naver_profiles


class NaverProfileTests(unittest.TestCase):
    """기존 계정 보존과 새 계정 분리를 검사합니다."""

    def test_legacy_and_named_profiles_are_discovered(self):
        """이전 단일 프로필과 새 계정 폴더를 함께 표시합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "legacy"
            profiles = root / "profiles"
            legacy.mkdir()
            (legacy / "Login Data").write_text("saved", encoding="utf-8")
            (profiles / "보조블로그").mkdir(parents=True)

            discovered = discover_naver_profiles(profiles, legacy)

            self.assertEqual(
                ["기존 기본 계정", "보조블로그"],
                [label for label, _ in discovered],
            )

    def test_existing_profile_can_be_selected_by_number(self):
        """목록 번호를 입력하면 해당 계정의 Chrome 폴더를 반환합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "개인블로그"
            profile_path.mkdir()
            with (
                patch(
                    "naver_profiles.discover_naver_profiles",
                    return_value=[("개인블로그", profile_path)],
                ),
                patch("builtins.input", return_value="1"),
            ):
                selected = choose_naver_profile()

            self.assertEqual(profile_path, selected)

    def test_new_profile_is_created_without_password(self):
        """새 계정은 별칭 폴더만 만들고 아이디나 비밀번호를 요구하지 않습니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_dir = Path(temp_dir) / "profiles"
            with (
                patch(
                    "naver_profiles.discover_naver_profiles",
                    return_value=[],
                ),
                patch.object(
                    naver_profiles,
                    "NAVER_BROWSER_PROFILES_DIR",
                    profiles_dir,
                ),
                patch("builtins.input", side_effect=["1", "업무/블로그"]),
            ):
                selected = choose_naver_profile()

            self.assertEqual(profiles_dir / "업무_블로그", selected)
            self.assertTrue(selected.is_dir())


# 이 파일을 직접 실행해도 테스트가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
