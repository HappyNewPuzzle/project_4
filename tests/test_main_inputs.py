"""생성 완료 후의 콘솔 선택이 글을 잃지 않고 재입력되는지 검증합니다."""

from __future__ import annotations

# 표준 테스트 도구와 사용자 입력 모의 기능을 사용합니다.
import unittest
from unittest.mock import patch

# 검증할 예/아니요 및 제목 선택 함수를 가져옵니다.
from main import ask_yes_no, choose_title


class MainInputTests(unittest.TestCase):
    """한글 키보드와 잘못된 번호 입력을 안전하게 처리하는지 검사합니다."""

    def test_korean_keyboard_y_key_is_accepted(self):
        """한글 입력 상태에서 y 키로 입력되는 `ㅛ`를 긍정으로 처리합니다."""

        with patch("builtins.input", return_value="ㅛ"):
            self.assertTrue(ask_yes_no("자동 배치할까요?"))

    def test_invalid_answer_retries_instead_of_exiting(self):
        """잘못된 답 뒤에 `ㅜ`를 입력하면 재질문 후 부정으로 처리합니다."""

        with patch("builtins.input", side_effect=["잘못된값", "ㅜ"]):
            self.assertFalse(ask_yes_no("자동 배치할까요?"))

    def test_invalid_title_number_retries(self):
        """범위 밖 번호와 문자를 입력해도 올바른 제목 선택까지 반복합니다."""

        titles = ["첫째", "둘째", "셋째", "넷째", "다섯째"]
        with patch("builtins.input", side_effect=["9", "문자", "3"]):
            self.assertEqual("셋째", choose_title(titles))


# 이 파일을 직접 실행해도 테스트가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
