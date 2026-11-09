"""도메인 오류 정의 (명세서 4.3절). 이 파일은 starter kit에 완성본으로 제공된다."""

from __future__ import annotations


class LibraryError(Exception):
    """책숲 도메인 오류의 기반 클래스.

    `code`는 대문자 스네이크 케이스 오류 코드, `str(err)`는 사용자에게 보여 줄 한국어 메시지다.
    """

    code: str = "LIBRARY_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BookNotFoundError(LibraryError):
    code = "BOOK_NOT_FOUND"


class MemberNotFoundError(LibraryError):
    code = "MEMBER_NOT_FOUND"


class MemberSuspendedError(LibraryError):
    code = "MEMBER_SUSPENDED"


class UnpaidFeeError(LibraryError):
    code = "UNPAID_FEE"


class NotAvailableError(LibraryError):
    code = "NOT_AVAILABLE"


class LoanLimitError(LibraryError):
    code = "LOAN_LIMIT"


class HoldNotAllowedError(LibraryError):
    code = "HOLD_NOT_ALLOWED"


class HoldDuplicateError(LibraryError):
    code = "HOLD_DUPLICATE"


class HoldLimitError(LibraryError):
    code = "HOLD_LIMIT"


class NoFeeError(LibraryError):
    code = "NO_FEE"


# 명세서에 고정된 메시지 템플릿. store.py는 반드시 이 템플릿으로 오류 메시지를 만든다.
MESSAGES: dict[str, str] = {
    "BOOK_NOT_FOUND": "도서를 찾을 수 없습니다: {book_id}",
    "MEMBER_NOT_FOUND": "회원을 찾을 수 없습니다: {member_id}",
    "MEMBER_SUSPENDED": "이용이 정지된 회원입니다: {member_id}",
    "UNPAID_FEE": "미납 연체료가 있어 대출할 수 없습니다: {fee}원",
    "NOT_AVAILABLE": "대출 가능한 재고가 없습니다: {book_id}",
    "LOAN_LIMIT": "대출 한도를 초과합니다: 현재 {current}권 + 요청 {requested}권 > 한도 {limit}권",
    "HOLD_NOT_ALLOWED": "대출 가능한 도서는 예약할 수 없습니다: {book_id}",
    "HOLD_DUPLICATE": "이미 예약한 도서입니다: {book_id}",
    "HOLD_LIMIT": "예약 한도를 초과합니다: 최대 {limit}권",
    "NO_FEE": "면제할 연체료가 없습니다: {member_id}",
}
