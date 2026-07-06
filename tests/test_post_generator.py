"""공통 글 생성과 ChatGPT 프롬프트 모드를 검증합니다."""

from __future__ import annotations

# 테스트 중 만든 파일을 자동으로 정리하는 임시 폴더를 사용합니다.
import tempfile
# 표준 라이브러리 테스트 도구를 사용해 별도 패키지 없이 실행합니다.
import unittest
# 임시 사진과 저장 파일 경로를 다룹니다.
from pathlib import Path
# 실제 출력 폴더 대신 테스트 폴더를 사용하도록 값을 교체합니다.
from unittest.mock import patch

# 테스트할 모듈 자체와 공개 객체를 가져옵니다.
import post_generator
from post_generator import (
    ReviewInput,
    build_chatgpt_prompt,
    create_layout_post,
    generate_post,
    save_chatgpt_prompt,
)


class FakeClient:
    """외부 AI를 호출하지 않고 정상적인 구조화 결과를 반환합니다."""

    def generate_post(self, instructions, user_prompt, image_paths):
        """공통 클라이언트 규격에 맞는 테스트 응답을 반환합니다."""

        return {
            "title_candidates": [f"제목 {number}" for number in range(1, 6)],
            "body": "테스트 블로그 본문입니다.",
            "tags": [f"태그{number}" for number in range(1, 11)],
        }


class IncompleteClient:
    """GPU 결과를 버리지 않고 보정하는 상황을 재현하는 테스트 클라이언트입니다."""

    def generate_post(self, instructions, user_prompt, image_paths):
        """제목과 태그가 부족하고 중복된 응답을 반환합니다."""

        return {
            "title_candidates": ["모델 제목", "모델 제목"],
            "body": "살려서 사용할 수 있는 블로그 본문입니다.",
            "tags": ["#사진리뷰", "사진리뷰", "방문후기"],
        }


class QwenStyleClient:
    """Qwen3.5가 실제로 반환한 별칭 키와 문단 배열 형식을 재현합니다."""

    def generate_post(self, instructions, user_prompt, image_paths):
        """title 키와 배열 body를 가진 응답을 반환합니다."""

        return {
            "title": [f"Qwen 제목 {number}" for number in range(1, 6)],
            "body": ["첫 번째 문단입니다.", "두 번째 문단입니다."],
            "tags": [f"Qwen태그{number}" for number in range(1, 11)],
        }


class PostGeneratorTests(unittest.TestCase):
    """ChatGPT 수동 모드와 공통 결과 변환을 검사합니다."""

    def setUp(self):
        """각 테스트마다 독립적인 임시 사진과 리뷰 정보를 준비합니다."""

        # 테스트가 끝나면 자동으로 삭제되는 임시 폴더를 만듭니다.
        self.temp_dir = tempfile.TemporaryDirectory()
        # 실제 사진 내용은 전송하지 않으므로 작은 가짜 JPG 파일이면 충분합니다.
        self.image_path = Path(self.temp_dir.name) / "food.jpg"
        self.image_path.write_bytes(b"test-image")
        # 모든 테스트에서 재사용할 정상 음식점 리뷰 입력입니다.
        self.review = ReviewInput(
            review_type="restaurant",
            name="테스트 식당",
            link="https://example.com/place",
            memo="음식이 따뜻하고 만족스러웠어요.",
            rating=4.5,
            image_paths=[self.image_path],
        )
        # 실제 settings.json과 같은 필수 스타일 키를 준비합니다.
        self.settings = {
            "tone": "친근한 말투",
            "emoji_style": "적당히 사용",
            "opening": "안녕하세요 😊",
            "closing": "읽어주셔서 감사합니다.",
            "link_text": "자세한 내용은 아래 링크에서 확인하세요.",
        }

    def tearDown(self):
        """테스트 중 생성된 임시 파일과 폴더를 정리합니다."""

        self.temp_dir.cleanup()

    def test_chatgpt_prompt_contains_review_and_output_format(self):
        """수동 프롬프트에 사용자 정보와 요구 결과 형식이 모두 포함됩니다."""

        prompt = build_chatgpt_prompt(self.review, self.settings)

        self.assertIn("테스트 식당", prompt)
        self.assertIn("첨부한 사진 1장", prompt)
        self.assertIn("[PHOTO_1]", prompt)
        self.assertIn("=== 제목 후보 5개 ===", prompt)
        self.assertIn("=== 네이버 블로그 태그 10개 ===", prompt)

    def test_chatgpt_prompt_without_paths_uses_attached_photos(self):
        """수동 모드는 사진 경로 없이 ChatGPT 첨부 사진 전체를 분석하게 합니다."""

        review_without_paths = ReviewInput(
            review_type=self.review.review_type,
            name=self.review.name,
            link=self.review.link,
            memo=self.review.memo,
            rating=self.review.rating,
            image_paths=[],
        )

        prompt = build_chatgpt_prompt(review_without_paths, self.settings)

        self.assertIn("ChatGPT에 첨부한 모든 사진", prompt)
        self.assertNotIn("사진 수: 0장", prompt)

    def test_common_generator_accepts_provider_independent_client(self):
        """공통 생성기는 OpenAI가 아닌 같은 규격의 클라이언트도 사용합니다."""

        post = generate_post(self.review, self.settings, FakeClient())

        self.assertEqual(5, len(post.title_candidates))
        self.assertEqual("테스트 블로그 본문입니다.", post.body)
        self.assertEqual(10, len(post.tags))

    def test_incomplete_title_and_tag_counts_are_completed_locally(self):
        """제목·태그 개수가 틀려도 모델 본문을 버리지 않고 로컬에서 보정합니다."""

        post = generate_post(self.review, self.settings, IncompleteClient())

        self.assertEqual(5, len(post.title_candidates))
        self.assertEqual(10, len(post.tags))
        self.assertEqual("모델 제목", post.title_candidates[0])
        self.assertEqual("사진리뷰", post.tags[0])
        self.assertEqual("살려서 사용할 수 있는 블로그 본문입니다.", post.body)
        self.assertEqual(len(post.tags), len(set(post.tags)))

    def test_qwen_alias_title_and_body_array_are_normalized(self):
        """Qwen의 title 별칭과 문단 배열을 정상 블로그 결과로 변환합니다."""

        post = generate_post(self.review, self.settings, QwenStyleClient())

        self.assertEqual("Qwen 제목 1", post.title_candidates[0])
        self.assertEqual(
            "첫 번째 문단입니다.\n\n두 번째 문단입니다.",
            post.body,
        )
        self.assertEqual(10, len(post.tags))

    def test_layout_post_contains_every_photo_and_editing_space(self):
        """AI 없는 빈 초안은 모든 사진과 직접 작성할 설명 공간을 만듭니다."""

        second_image = Path(self.temp_dir.name) / "food2.jpg"
        second_image.write_bytes(b"second-image")
        review = ReviewInput(
            review_type=self.review.review_type,
            name=self.review.name,
            link=self.review.link,
            memo=self.review.memo,
            rating=self.review.rating,
            image_paths=[self.image_path, second_image],
        )

        post = create_layout_post(review, self.settings)

        self.assertIn("[PHOTO_1]", post.body)
        self.assertIn("[PHOTO_2]", post.body)
        self.assertIn("✏️ 사진 1 설명을 입력하세요.", post.body)
        self.assertIn("✏️ 사진 2 설명을 입력하세요.", post.body)
        self.assertIn(self.review.link, post.body)
        self.assertEqual(5, len(post.title_candidates))
        self.assertEqual(10, len(post.tags))

    def test_chatgpt_prompt_file_is_saved_in_selected_directory(self):
        """프롬프트 파일에 사진 체크리스트와 실제 프롬프트가 저장됩니다."""

        prompt = build_chatgpt_prompt(self.review, self.settings)
        test_output_dir = Path(self.temp_dir.name) / "generated_prompts"

        with patch.object(post_generator, "PROMPT_OUTPUT_DIR", test_output_dir):
            output_path = save_chatgpt_prompt(prompt, self.review)

        saved_text = output_path.read_text(encoding="utf-8")
        self.assertTrue(output_path.exists())
        self.assertIn(str(self.image_path), saved_text)
        self.assertIn(prompt, saved_text)


# 이 테스트 파일을 직접 실행해도 unittest가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
