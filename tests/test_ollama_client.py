"""실제 Ollama 설치 없이 REST 요청과 응답 처리를 검증합니다."""

from __future__ import annotations

# 가짜 Ollama 응답을 JSON 바이트로 만드는 데 사용합니다.
import json
# 테스트 사진을 자동 정리되는 임시 폴더에 만듭니다.
import tempfile
# 표준 unittest 실행기와 모의 객체 기능을 사용합니다.
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 검증할 Ollama 클라이언트를 가져옵니다.
from ollama_client import BlogOllamaClient


class OllamaClientTests(unittest.TestCase):
    """Vision 이미지와 JSON Schema가 올바르게 요청되는지 검사합니다."""

    def test_generate_post_sends_images_and_parses_structured_result(self):
        """사진은 Base64로 전송되고 message.content의 JSON은 딕셔너리가 됩니다."""

        # 테스트 종료 시 파일이 자동으로 삭제되는 임시 폴더를 사용합니다.
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "product.jpg"
            image_path.write_bytes(b"image-bytes")
            expected = {
                "title_candidates": [f"제목 {number}" for number in range(1, 6)],
                "body": "상품 리뷰 본문",
                "tags": [f"태그{number}" for number in range(1, 11)],
            }
            # urlopen의 컨텍스트 관리자와 read 결과를 실제 응답처럼 구성합니다.
            response = MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps(
                {"message": {"content": json.dumps(expected, ensure_ascii=False)}},
                ensure_ascii=False,
            ).encode("utf-8")

            # 실제 localhost 통신 대신 준비한 가짜 응답을 반환합니다.
            with patch("ollama_client.urlopen", return_value=response) as mocked_urlopen:
                client = BlogOllamaClient("http://localhost:11434", "gemma3:4b")
                result = client.generate_post(
                    "작성 규칙",
                    "상품 리뷰를 작성해주세요.",
                    [image_path],
                )

            # urlopen에 전달된 Request 객체에서 실제 JSON 요청을 확인합니다.
            request = mocked_urlopen.call_args.args[0]
            request_body = json.loads(request.data.decode("utf-8"))
            self.assertEqual(expected, result)
            self.assertEqual("gemma3:4b", request_body["model"])
            self.assertTrue(request_body["messages"][1]["images"][0])
            self.assertEqual("object", request_body["format"]["type"])
            self.assertFalse(request_body["stream"])
            self.assertFalse(request_body["think"])
            self.assertEqual(32_768, request_body["options"]["num_ctx"])

    def test_markdown_json_code_fence_is_recovered(self):
        """모델이 JSON을 코드 블록으로 감싸도 내부 객체를 정상적으로 읽습니다."""

        content = """```json
{"title_candidates":["1","2","3","4","5"],"body":"본문","tags":["1","2","3","4","5","6","7","8","9","10"]}
```"""

        result = BlogOllamaClient._parse_structured_content(content)

        self.assertEqual("본문", result["body"])
        self.assertEqual(5, len(result["title_candidates"]))

    def test_invalid_json_is_retried_once(self):
        """첫 응답이 잘린 JSON이면 같은 요청을 강화된 지침으로 한 번 재시도합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "product.jpg"
            image_path.write_bytes(b"image")
            expected = {
                "title_candidates": [f"제목 {number}" for number in range(1, 6)],
                "body": "재시도 후 정상 본문",
                "tags": [f"태그{number}" for number in range(1, 11)],
            }
            # 첫 서버 응답은 닫는 괄호가 없는 잘린 JSON을 반환합니다.
            first_response = MagicMock()
            first_response.__enter__.return_value.read.return_value = json.dumps(
                {"message": {"content": '{"title_candidates": ["잘린 응답"'}},
                ensure_ascii=False,
            ).encode("utf-8")
            # 두 번째 서버 응답은 완전한 구조화 JSON을 반환합니다.
            second_response = MagicMock()
            second_response.__enter__.return_value.read.return_value = json.dumps(
                {"message": {"content": json.dumps(expected, ensure_ascii=False)}},
                ensure_ascii=False,
            ).encode("utf-8")

            with patch(
                "ollama_client.urlopen",
                side_effect=[first_response, second_response],
            ) as mocked_urlopen:
                client = BlogOllamaClient("http://localhost:11434", "gemma3:4b")
                result = client.generate_post("규칙", "상품 후기", [image_path])

            self.assertEqual(expected, result)
            self.assertEqual(2, mocked_urlopen.call_count)
            second_request = mocked_urlopen.call_args_list[1].args[0]
            second_body = json.loads(second_request.data.decode("utf-8"))
            self.assertIn("이전 응답은 JSON 형식", second_body["messages"][1]["content"])


# 이 테스트 파일을 직접 실행해도 unittest가 시작되게 합니다.
if __name__ == "__main__":
    unittest.main()
