from __future__ import annotations

from retrieval import hybrid_query


class FakeCollection:
    def __init__(self) -> None:
        self.documents = [
            "Ticket P2 phản hồi sau 90 phút.",
            "Escalation P1: tự động escalate nếu không có phản hồi trong 10 phút.",
            "Laptop mới được cấp trong ngày onboarding.",
            "Thông báo stakeholder P1: update mỗi 30 phút cho đến khi resolve.",
        ]

    def count(self) -> int:
        return len(self.documents)

    def query(self, **_: object) -> dict[str, list[list[object]]]:
        return {
            "documents": [self.documents],
            "metadatas": [[{"doc_id": "sla"} for _ in self.documents]],
            "distances": [[0.1, 0.3, 0.1, 0.3]],
            "ids": [["p2", "p1-escalate", "laptop", "p1-update"]],
        }


def test_hybrid_query_reranks_escalation_by_query_coverage() -> None:
    result = hybrid_query(
        FakeCollection(),
        "Ticket P1 tự động chuyển cấp nếu không phản hồi sau bao lâu?",
        2,
    )

    assert result["ids"][0][0] == "p1-escalate"


def test_hybrid_query_normalizes_update_and_progress_terms() -> None:
    result = hybrid_query(
        FakeCollection(),
        "Sự cố P1 cần cập nhật tiến độ mỗi bao lâu?",
        2,
    )

    assert result["ids"][0][0] == "p1-update"
