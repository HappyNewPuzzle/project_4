"""ChatGPT에 붙여넣을 프롬프트를 Windows 클립보드에 복사합니다."""

from __future__ import annotations

# Python 기본 GUI 도구의 클립보드 기능만 사용하며 화면 창은 표시하지 않습니다.
import tkinter


class ClipboardError(Exception):
    """클립보드 접근에 실패했을 때 발생합니다."""


def copy_to_clipboard(text: str) -> None:
    """문자열을 시스템 클립보드에 복사하고 즉시 붙여넣을 수 있게 합니다."""

    try:
        # 숨겨진 Tk 객체를 만들어 운영체제 클립보드에 접근합니다.
        root = tkinter.Tk()
        # 실제 GUI 창은 필요하지 않으므로 바로 숨깁니다.
        root.withdraw()
        # 이전 클립보드 내용을 비웁니다.
        root.clipboard_clear()
        # 한글과 이모티콘을 포함한 새 프롬프트를 추가합니다.
        root.clipboard_append(text)
        # 창을 닫은 뒤에도 내용이 유지되도록 Windows에 변경 내용을 반영합니다.
        root.update()
        # 사용이 끝난 숨김 창과 관련 자원을 정리합니다.
        root.destroy()
    except tkinter.TclError as exc:
        # 원격 세션이나 클립보드 잠금 문제를 프로그램 전용 오류로 변환합니다.
        raise ClipboardError(f"클립보드에 복사할 수 없습니다: {exc}") from exc
