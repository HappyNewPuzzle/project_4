"""상품·가게 내 템플릿 슬롯에 사진이 올바르게 나뉘는지 검증합니다."""

from __future__ import annotations

# 테스트 사진을 실행 후 자동 정리합니다.
import tempfile
# 표준 테스트 도구와 경로 기능을 사용합니다.
import unittest
from pathlib import Path

# 템플릿 레이아웃 생성 기능과 공통 리뷰 입력을 가져옵니다.
from naver_template_layout import build_naver_template_layout
from post_generator import InputError, ReviewInput


class NaverTemplateLayoutTests(unittest.TestCase):
    """사진 순서, 템플릿 이름, 구간 합계 검증을 검사합니다."""

    def setUp(self):
        """각 테스트에서 사용할 여섯 장의 임시 사진을 만듭니다."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.images: list[Path] = []
        for number in range(1, 7):
            image_path = Path(self.temp_dir.name) / f"{number}.jpg"
            image_path.write_bytes(f"image-{number}".encode())
            self.images.append(image_path)

    def tearDown(self):
        """테스트 사진 폴더를 정리합니다."""

        self.temp_dir.cleanup()

    def test_restaurant_photos_are_split_without_changing_order(self):
        """외부·내부·메뉴·음식 구간에 입력 순서대로 사진을 배정합니다."""

        review = ReviewInput(
            review_type="restaurant",
            name="테스트 카페",
            link="https://example.com/cafe",
            memo="수제 와플",
            rating=4.0,
            image_paths=self.images,
        )

        layout = build_naver_template_layout(review, [1, 2, 1, 2])

        self.assertEqual("가게리뷰_자동", layout.template_name)
        self.assertEqual(
            self.images[:1],
            layout.photo_slots["[[EXTERIOR_PHOTOS]]"],
        )
        self.assertEqual(
            self.images[1:3],
            layout.photo_slots["[[INTERIOR_PHOTOS]]"],
        )
        self.assertEqual(
            self.images[4:],
            layout.photo_slots["[[FOOD_PHOTOS]]"],
        )

    def test_product_photos_are_split_into_delivery_and_details(self):
        """상품 사진을 배송·포장과 상세·사용 사진으로 나눕니다."""

        review = ReviewInput(
            review_type="product",
            name="테스트 상품",
            link="https://example.com/product",
            memo="직접 구매",
            rating=5.0,
            image_paths=self.images,
        )

        layout = build_naver_template_layout(review, [2, 4])

        self.assertEqual("상품리뷰_자동", layout.template_name)
        self.assertEqual(
            self.images[:2],
            layout.photo_slots["[[DELIVERY_PHOTOS]]"],
        )
        self.assertEqual(
            self.images[2:],
            layout.photo_slots["[[DETAIL_PHOTOS]]"],
        )

    def test_photo_section_total_must_match_input_count(self):
        """구간 사진 합계가 실제 사진 수와 다르면 브라우저 실행 전에 중단합니다."""

        review = ReviewInput(
            review_type="product",
            name="테스트 상품",
            link="https://example.com/product",
            memo="메모",
            rating=3.0,
            image_paths=self.images,
        )

        with self.assertRaises(InputError):
            build_naver_template_layout(review, [1, 2])


# 이 파일을 직접 실행해도 테스트가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
