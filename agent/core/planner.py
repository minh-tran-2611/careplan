import re
import unicodedata


def deidentify(value: str) -> str:
    """Lọc cơ bản email và số điện thoại. Không thay thế ẩn danh thủ công."""
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email đã ẩn]", value or "", flags=re.I)
    return re.sub(r"(?:\+84|0)(?:[ .-]?\d){9,10}\b", "[số điện thoại đã ẩn]", value)


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D").lower()


_PLAN_VERB = r"(lap|tao|soan|lam|viet|xay dung|dua ra|de xuat|len)"
_PLAN_PATTERNS = [
    rf"\b{_PLAN_VERB}\b.{{0,40}}\bke hoach\b",       # "lập bảng kế hoạch", "soạn giúp kế hoạch"
    r"\bbang ke hoach\b",                              # "bảng kế hoạch chăm sóc…"
    r"\bke hoach (cham soc|dieu duong)\b.{0,20}\b(cho|nguoi benh|benh nhan|ca nay)\b",
    r"\bcare ?plan\b",
]


def wants_plan(message: str, mode: str = "auto") -> bool:
    """Câu hỏi có phải là yêu cầu lập bảng kế hoạch điều dưỡng không."""
    if mode in ("plan", "answer"):
        return mode == "plan"
    text = _plain(message)
    return any(re.search(p, text) for p in _PLAN_PATTERNS)


def build_query(message: str, history: list, journal: list, plan: bool = False) -> str:
    """Truy vấn tìm nguồn.

    Hỏi thường: câu hỏi + câu hỏi trước (cho câu hỏi nối tiếp) + ghi chép nhật ký mới nhất.
    Lập kế hoạch: như trên nhưng lấy tối đa 3 ghi chép gần nhất, vì bảng phải bám diễn biến người bệnh.
    """
    parts = [message]
    previous = [m.content for m in history if m.role == "user"]
    if previous:
        parts.append(previous[-1][: 300 if plan else 500])
    if journal:
        recent = journal[-3:] if plan else journal[-1:]
        parts.append(" ".join(e.text for e in recent)[: 1200 if plan else 400])
    return deidentify(" ".join(parts))
