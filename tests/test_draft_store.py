"""오류 후 마지막 콘솔 입력을 안전하게 저장하고 복원하는지 검증합니다."""

from __future__ import annotations

# 테스트 파일을 자동으로 정리할 임시 폴더를 사용합니다.
import tempfile
# 표준 테스트 도구와 경로 기능을 사용합니다.
import unittest
from pathlib import Path
# 실제 data 폴더 대신 임시 체크포인트 경로를 사용합니다.
from unittest.mock import patch

# 검증할 모듈과 공통 리뷰 입력 객체를 가져옵니다.
import draft_store
from draft_store import clear_last_input, load_last_input, save_last_input
from post_generator import ReviewInput


class DraftStoreTests(unittest.TestCase):
    """저장·복원·정상 완료 삭제 흐름을 검사합니다."""

    def test_review_input_is_restored_after_failure_checkpoint(self):
        """입력 전체와 사진 순서가 JSON 저장 뒤 동일하게 복원됩니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            first_image = folder / "1.jpg"
            second_image = folder / "2.jpg"
            first_image.write_bytes(b"one")
            second_image.write_bytes(b"two")
            checkpoint = folder / "last_input.json"
            review = ReviewInput(
                review_type="product",
                name="복원 상품",
                link="https://example.com/product",
                memo="다시 입력하지 않을 메모",
                rating=4.5,
                image_paths=[first_image, second_image],
            )

            with patch.object(draft_store, "LAST_INPUT_PATH", checkpoint):
                save_last_input("ollama", review)
                restored = load_last_input()

            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual("ollama", restored[0])
            self.assertEqual(review, restored[1])

    def test_successful_run_can_clear_checkpoint(self):
        """정상 완료 시 임시 입력 파일을 삭제할 수 있습니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint = Path(temp_dir) / "last_input.json"
            review = ReviewInput(
                review_type="restaurant",
                name="테스트 식당",
                link="https://example.com/place",
                memo="테스트 메모",
                rating=4.0,
                image_paths=[],
            )

            with patch.object(draft_store, "LAST_INPUT_PATH", checkpoint):
                save_last_input("chatgpt", review)
                clear_last_input()
                restored = load_last_input()

            self.assertIsNone(restored)


# 이 파일을 직접 실행해도 테스트가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
