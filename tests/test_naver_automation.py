"""네이버 편집 자동화가 사진 위치 표시를 안전하게 해석하는지 검증합니다."""

from __future__ import annotations

# 임시 사진 파일을 테스트 뒤 자동 정리합니다.
import tempfile
# 표준 테스트 도구와 파일 경로 기능을 사용합니다.
import unittest
from pathlib import Path

# 브라우저 실행 전에 검증할 블록 변환 기능과 오류를 가져옵니다.
from naver_automation import NaverAutomationError, build_editor_blocks


class NaverAutomationTests(unittest.TestCase):
    """모델 본문의 사진 표시와 실제 사진 연결을 검사합니다."""

    def test_build_editor_blocks_preserves_text_and_image_order(self):
        """표준 사진 표시를 텍스트·사진·텍스트 순서로 정확히 바꿉니다."""

        # 테스트 종료 시 자동 삭제되는 두 사진 경로를 준비합니다.
        with tempfile.TemporaryDirectory() as temp_dir:
            first_image = Path(temp_dir) / "first.jpg"
            second_image = Path(temp_dir) / "second.jpg"
            first_image.write_bytes(b"first")
            second_image.write_bytes(b"second")
            body = (
                "안녕하세요.\n\n"
                "[PHOTO_1]\n첫 번째 음식 사진 설명입니다.\n\n"
                "[PHOTO_2]\n두 번째 매장 사진 설명입니다.\n\n"
                "전체적인 만족도는 보통이었습니다."
            )

            blocks = build_editor_blocks(body, [first_image, second_image])

            self.assertEqual(
                ["text", "image", "text", "image", "text"],
                [block.kind for block in blocks],
            )
            self.assertEqual(first_image, blocks[1].image_path)
            self.assertIn("첫 번째 음식", blocks[2].text)
            self.assertEqual(second_image, blocks[3].image_path)

    def test_korean_photo_alias_is_supported(self):
        """작은 로컬 모델이 출력한 `(사진1)` 표기도 안전하게 인식합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "photo.jpg"
            image_path.write_bytes(b"photo")

            blocks = build_editor_blocks(
                "도입 문장\n(사진1)\n사진 설명\n마무리",
                [image_path],
            )

            self.assertEqual("image", blocks[1].kind)
            self.assertEqual(image_path, blocks[1].image_path)

    def test_duplicate_marker_inserts_image_only_once(self):
        """작은 모델이 같은 표시를 반복해도 사진은 최초 위치에 한 번만 넣습니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "photo.jpg"
            image_path.write_bytes(b"photo")

            blocks = build_editor_blocks(
                "도입\n[PHOTO_1] 첫 설명\n[PHOTO_1]\n추가 설명",
                [image_path],
            )

            image_blocks = [block for block in blocks if block.kind == "image"]
            self.assertEqual(1, len(image_blocks))
            self.assertEqual(image_path, image_blocks[0].image_path)

    def test_missing_photo_marker_stops_before_browser(self):
        """사진 표시가 빠진 본문은 잘못 배치하지 않고 오류로 중단합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            images = [Path(temp_dir) / "one.jpg", Path(temp_dir) / "two.jpg"]

            with self.assertRaises(NaverAutomationError):
                build_editor_blocks("사진 표시가 없는 본문", images)

    def test_trailing_missing_markers_are_appended_after_last_description(self):
        """모델이 뒤쪽 사진 표시만 생략하면 남은 사진을 입력 순서대로 보완합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            images = [
                Path(temp_dir) / f"{number}.jpg"
                for number in range(1, 5)
            ]
            body = (
                "도입\n\n"
                "[PHOTO_1]\n첫 사진 설명\n\n"
                "[PHOTO_2]\n두 번째 사진 설명\n\n"
                "전체적인 마무리 문장"
            )

            blocks = build_editor_blocks(body, images)

            image_blocks = [block for block in blocks if block.kind == "image"]
            self.assertEqual(images, [block.image_path for block in image_blocks])
            # 누락 사진은 총평보다 앞에 배치해 링크·마무리 뒤로 밀리지 않게 합니다.
            self.assertEqual("text", blocks[-1].kind)
            self.assertIn("전체적인 마무리", blocks[-1].text)

    def test_non_contiguous_markers_still_raise_error(self):
        """중간 번호가 빠진 경우에는 잘못된 사진 연결을 막기 위해 중단합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            images = [
                Path(temp_dir) / f"{number}.jpg"
                for number in range(1, 4)
            ]

            with self.assertRaises(NaverAutomationError):
                build_editor_blocks(
                    "[PHOTO_1]\n첫 사진\n\n[PHOTO_3]\n세 번째 사진",
                    images,
                )


# 이 파일을 직접 실행해도 테스트가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
