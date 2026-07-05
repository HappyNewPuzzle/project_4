"""네이버 스마트에디터에 제목, 사진, 본문을 반자동으로 배치합니다.

공식 글쓰기 API가 없으므로 Playwright로 사용자가 보는 Chrome을 조작합니다.
사용자가 직접 로그인하고 최종 내용을 확인하며, 이 모듈은 발행 버튼을
찾거나 누르지 않습니다.
"""

from __future__ import annotations

# 모델 본문에 들어간 사진 위치 표시를 찾아 글과 사진 블록으로 나눕니다.
import re
# 편집기에 넣을 텍스트와 사진 블록을 명확한 객체로 표현합니다.
from dataclasses import dataclass
# Chrome 프로필과 업로드할 사진 경로를 처리합니다.
from pathlib import Path
# 페이지나 iframe처럼 locator 기능을 제공하는 객체의 자료형을 표현합니다.
from typing import Any

# Playwright의 동기식 Python API로 실제 Chrome 브라우저를 조작합니다.
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, sync_playwright


class NaverAutomationError(Exception):
    """네이버 편집기 탐색이나 사진·본문 배치에 실패했을 때 발생합니다."""


@dataclass(frozen=True)
class EditorBlock:
    """네이버 편집기에 순서대로 넣을 텍스트 또는 사진 하나를 나타냅니다."""

    # `text` 또는 `image` 중 어떤 종류의 블록인지 표시합니다.
    kind: str
    # 텍스트 블록의 본문이며 사진 블록에서는 비어 있습니다.
    text: str = ""
    # 사진 블록의 로컬 경로이며 텍스트 블록에서는 None입니다.
    image_path: Path | None = None


# 모델이 정확한 표기 대신 자주 사용하는 `(사진1)`과 `[사진 1]`도 허용합니다.
PHOTO_MARKER_ALIASES = re.compile(r"(?:\(사진\s*(\d+)\)|\[사진\s*(\d+)\])")
# 정규화된 사진 표시는 줄 안팎 어디에 있든 `[PHOTO_숫자]` 형태로 찾습니다.
PHOTO_MARKER = re.compile(r"\[PHOTO_(\d+)\]")

# 스마트에디터 버전 차이를 고려한 제목 입력 영역 후보입니다.
TITLE_SELECTORS = (
    ".se-section-documentTitle .se-text-paragraph",
    ".se-documentTitle .se-text-paragraph",
    ".se-section-title .se-text-paragraph",
    "[contenteditable='true'][data-placeholder*='제목']",
    "[contenteditable='true'][aria-label*='제목']",
    "textarea[placeholder*='제목']",
)
# 제목을 제외한 본문 문단을 찾기 위한 입력 영역 후보입니다.
CONTENT_SELECTORS = (
    ".se-main-container .se-section-text .se-text-paragraph",
    ".se-section-text .se-text-paragraph",
    ".se-main-container .se-component.se-text .se-text-paragraph",
    ".se-main-container [contenteditable='true'].se-text-paragraph",
    "[contenteditable='true'][data-placeholder*='내용']",
    "[contenteditable='true'][aria-label*='본문']",
)
# 사진 파일 선택 창을 여는 툴바 버튼 후보입니다.
PHOTO_BUTTON_SELECTORS = (
    "button.se-image-toolbar-button",
    "button[aria-label*='사진']",
    "button:has-text('사진')",
)


def build_editor_blocks(body: str, image_paths: list[Path]) -> list[EditorBlock]:
    """사진 표시가 포함된 모델 본문을 네이버 입력 순서의 블록으로 바꿉니다."""

    # `(사진1)` 같은 별칭을 표준 `[PHOTO_1]` 한 줄로 먼저 통일합니다.
    normalized = PHOTO_MARKER_ALIASES.sub(
        lambda match: f"\n[PHOTO_{match.group(1) or match.group(2)}]\n",
        body,
    )
    # 본문에 등장하는 모든 표준 사진 표시와 위치를 찾습니다.
    matches = list(PHOTO_MARKER.finditer(normalized))
    # 모델이 같은 사진 표시를 반복해도 실제 사진은 최초 한 번만 배치합니다.
    unique_marker_numbers: list[int] = []
    for match in matches:
        marker_number = int(match.group(1))
        if marker_number not in unique_marker_numbers:
            unique_marker_numbers.append(marker_number)
    # 최초 등장 번호는 입력 사진 수와 같은 1부터 N까지의 순서여야 합니다.
    expected_numbers = list(range(1, len(image_paths) + 1))
    if unique_marker_numbers != expected_numbers:
        raise NaverAutomationError(
            "본문의 사진 위치 표시가 올바르지 않습니다. "
            f"필요한 순서: {expected_numbers}, 실제 고유 순서: {unique_marker_numbers}"
        )

    # 표시 앞뒤의 텍스트와 실제 사진을 순서대로 담을 목록입니다.
    blocks: list[EditorBlock] = []
    cursor = 0
    inserted_numbers: set[int] = set()
    for match in matches:
        # 현재 사진 표시 앞에 있는 인사말이나 이전 사진 설명을 가져옵니다.
        text_before = normalized[cursor : match.start()].strip()
        if text_before:
            blocks.append(EditorBlock(kind="text", text=text_before))
        marker_number = int(match.group(1))
        # 같은 번호가 반복되면 표시만 제거하고 사진은 다시 넣지 않습니다.
        if marker_number not in inserted_numbers:
            # 표시 자체 대신 해당 번호와 연결된 실제 로컬 사진을 배치합니다.
            blocks.append(
                EditorBlock(
                    kind="image",
                    image_path=image_paths[marker_number - 1],
                )
            )
            inserted_numbers.add(marker_number)
        cursor = match.end()

    # 마지막 사진 표시 뒤의 총평, 링크, 마무리 문구도 추가합니다.
    remaining_text = normalized[cursor:].strip()
    if remaining_text:
        blocks.append(EditorBlock(kind="text", text=remaining_text))
    return blocks


class NaverBlogAutomator:
    """전용 Chrome 프로필에서 네이버 글쓰기 초안을 채우는 자동화 도구입니다."""

    def __init__(self, write_url: str, profile_dir: Path) -> None:
        # 네이버 글쓰기 진입 주소를 저장합니다.
        self.write_url = write_url
        # 로그인 쿠키를 재사용할 전용 Chrome 프로필 경로를 저장합니다.
        self.profile_dir = profile_dir

    @staticmethod
    def _scopes(page: Page) -> list[Any]:
        """메인 페이지와 모든 iframe을 locator 검색 대상으로 반환합니다."""

        # 네이버 편집기가 iframe 안에 있더라도 같은 검색 로직을 사용할 수 있습니다.
        return [page, *page.frames]

    def _find_first_visible(
        self, page: Page, selectors: tuple[str, ...]
    ) -> Locator:
        """여러 selector와 frame 중 화면에 보이는 첫 요소를 찾습니다."""

        # 각 frame에서 안정적인 selector부터 순서대로 검사합니다.
        for scope in self._scopes(page):
            for selector in selectors:
                locator = scope.locator(selector)
                # 같은 selector가 여러 문단을 찾으면 첫 번째 보이는 요소를 사용합니다.
                for index in range(locator.count()):
                    candidate = locator.nth(index)
                    try:
                        # 화면 이동 중 분리된 요소는 건너뛰고 다음 후보를 검사합니다.
                        if candidate.is_visible():
                            return candidate
                    except PlaywrightError:
                        continue
        raise NaverAutomationError(
            "네이버 스마트에디터 입력 영역을 찾지 못했습니다. "
            "글쓰기 화면이 완전히 열린 상태인지 확인해주세요."
        )

    def _page_has_editor(self, page: Page) -> bool:
        """한 탭 안에 제목과 본문 영역이 모두 보이는지 부작용 없이 검사합니다."""

        try:
            # 두 입력 영역을 모두 찾을 수 있을 때만 실제 편집기 탭으로 판단합니다.
            self._find_first_visible(page, TITLE_SELECTORS)
            self._find_first_visible(page, CONTENT_SELECTORS)
            return True
        except NaverAutomationError:
            return False

    def _select_editor_page(self, context: Any) -> Page:
        """로그인 뒤 열려 있는 모든 탭에서 실제 스마트에디터 탭을 선택합니다."""

        # 로그인 과정에서 새 탭이 열릴 수 있으므로 가장 최근 탭부터 검사합니다.
        for candidate in reversed(context.pages):
            try:
                # 아직 로딩 중인 DOM이 안정될 짧은 시간을 줍니다.
                candidate.wait_for_timeout(500)
                if self._page_has_editor(candidate):
                    return candidate
            except PlaywrightError:
                # 닫혔거나 이동 중인 탭은 무시하고 다음 탭을 검사합니다.
                continue

        # 다음 오류 신고에서 원인을 좁힐 수 있도록 URL과 요소 개수만 수집합니다.
        diagnostics: list[str] = []
        for page_index, candidate in enumerate(context.pages):
            try:
                editable_count = sum(
                    frame.locator("[contenteditable='true']").count()
                    for frame in candidate.frames
                )
                paragraph_count = sum(
                    frame.locator(".se-text-paragraph").count()
                    for frame in candidate.frames
                )
                diagnostics.append(
                    f"탭{page_index + 1} URL={candidate.url}, "
                    f"contenteditable={editable_count}, "
                    f"se-text-paragraph={paragraph_count}"
                )
            except PlaywrightError:
                diagnostics.append(f"탭{page_index + 1}=진단 실패")
        diagnostic_text = " | ".join(diagnostics) or "열린 탭 없음"
        raise NaverAutomationError(
            "네이버 스마트에디터 제목·본문 영역을 찾지 못했습니다. "
            "새 글쓰기 화면인지 확인해주세요. "
            f"[진단: {diagnostic_text}]"
        )

    def _find_last_visible_content(self, page: Page) -> Locator:
        """현재 글의 가장 마지막 본문 문단을 찾아 커서를 이어서 입력합니다."""

        # 사진 업로드 뒤 새 문단이 생기므로 뒤에서부터 보이는 문단을 찾습니다.
        for scope in reversed(self._scopes(page)):
            for selector in CONTENT_SELECTORS:
                locator = scope.locator(selector)
                for index in range(locator.count() - 1, -1, -1):
                    candidate = locator.nth(index)
                    if candidate.is_visible():
                        return candidate
        raise NaverAutomationError("본문의 마지막 입력 위치를 찾지 못했습니다.")

    def _fill_title(self, page: Page, title: str) -> None:
        """제목 영역의 기존 내용을 지우고 사용자가 고른 제목을 입력합니다."""

        # 여러 스마트에디터 버전 중 현재 화면에 보이는 제목 영역을 찾습니다.
        title_locator = self._find_first_visible(page, TITLE_SELECTORS)
        # contenteditable 요소에서도 동작하도록 키보드 방식으로 내용을 교체합니다.
        title_locator.click()
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(title)

    def _append_text(self, page: Page, text: str, first_text: bool) -> None:
        """현재 본문 끝에 새 문단을 만든 뒤 텍스트를 입력합니다."""

        if first_text:
            # 빈 글의 첫 문단은 placeholder가 있는 최초 본문 영역을 사용합니다.
            paragraph = self._find_first_visible(page, CONTENT_SELECTORS)
            paragraph.click()
        else:
            # 사진이나 이전 문단 다음에는 가장 마지막 본문 문단으로 이동합니다.
            paragraph = self._find_last_visible_content(page)
            paragraph.click()
            page.keyboard.press("End")
            page.keyboard.press("Enter")
        # 사람의 키 입력처럼 한글 본문을 현재 커서 위치에 넣습니다.
        page.keyboard.insert_text(text)

    def _append_image(self, page: Page, image_path: Path) -> None:
        """현재 본문 끝의 커서 위치에 로컬 사진 한 장을 업로드합니다."""

        # 사진이 마지막 문단 다음에 들어가도록 현재 글의 끝으로 커서를 옮깁니다.
        paragraph = self._find_last_visible_content(page)
        paragraph.click()
        page.keyboard.press("End")
        page.keyboard.press("Enter")
        # 현재 스마트에디터에서 보이는 사진 도구 버튼을 찾습니다.
        photo_button = self._find_first_visible(page, PHOTO_BUTTON_SELECTORS)
        try:
            # 버튼이 만드는 동적 파일 선택 창을 Playwright가 직접 가로챕니다.
            with page.expect_file_chooser(timeout=10_000) as chooser_info:
                photo_button.click()
            # 운영체제 파일 선택 대화상자를 띄우지 않고 해당 사진을 지정합니다.
            chooser_info.value.set_files(str(image_path))
            # 네이버가 사진 업로드와 에디터 컴포넌트 생성을 마칠 시간을 줍니다.
            page.wait_for_timeout(2_000)
        except PlaywrightError as exc:
            raise NaverAutomationError(
                f"사진 업로드 창을 처리하지 못했습니다 ({image_path.name}): {exc}"
            ) from exc

    def fill_draft(
        self,
        title: str,
        body: str,
        image_paths: list[Path],
    ) -> None:
        """브라우저를 열고 제목·사진·본문을 배치한 뒤 사용자 확인을 기다립니다."""

        # 브라우저를 열기 전에 사진 표시가 모두 있는지 검증합니다.
        blocks = build_editor_blocks(body, image_paths)
        # 프로필 폴더가 없으면 첫 실행에 자동으로 생성합니다.
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as playwright:
                # 기본 Chrome 프로필과 충돌하지 않는 자동화 전용 프로필을 사용합니다.
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    channel="chrome",
                    headless=False,
                    no_viewport=True,
                )
                # 프로필에 빈 탭이 이미 있으면 재사용하고 없으면 새 탭을 만듭니다.
                page = context.pages[0] if context.pages else context.new_page()
                # 로그인 상태에 따라 로그인 또는 글쓰기 화면으로 이동합니다.
                page.goto(self.write_url, wait_until="domcontentloaded", timeout=60_000)
                print(
                    "\n브라우저에서 네이버 로그인과 글쓰기 화면을 확인해주세요.\n"
                    "제목과 본문을 입력할 수 있는 화면이 보이면 콘솔로 돌아오세요."
                )
                input("준비되면 Enter를 누르세요: ")
                # 로그인 중 새 탭이 생겼다면 실제 편집기 탭으로 자동 전환합니다.
                page = self._select_editor_page(context)
                # 사용자가 고른 제목을 먼저 입력합니다.
                self._fill_title(page, title)
                # 첫 텍스트인지 추적해 빈 본문과 후속 문단 입력 방식을 구분합니다.
                first_text = True
                for block in blocks:
                    if block.kind == "text":
                        self._append_text(page, block.text, first_text)
                        first_text = False
                    elif block.image_path is not None:
                        self._append_image(page, block.image_path)

                print(
                    "\n네이버 편집기에 제목, 사진, 본문 배치를 완료했습니다.\n"
                    "브라우저에서 내용을 검토하고 태그·발행 설정을 직접 입력해주세요.\n"
                    "프로그램은 발행 버튼을 누르지 않습니다."
                )
                # 사용자가 검토하거나 임시저장할 동안 브라우저가 닫히지 않게 기다립니다.
                input("브라우저 작업을 마친 뒤 Enter를 누르면 프로그램이 종료됩니다: ")
                # 전용 브라우저 프로필에 로그인 상태를 안전하게 기록하고 닫습니다.
                context.close()
        except PlaywrightError as exc:
            raise NaverAutomationError(f"Chrome 자동화 실행에 실패했습니다: {exc}") from exc
