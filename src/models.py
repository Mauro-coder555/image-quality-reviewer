from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ImageStatus(str, Enum):
    OK = "OK"
    REVIEW = "Review"
    BROKEN = "Broken"


@dataclass
class Evidence:
    check: str
    passed: bool
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageResult:
    path: Path
    status: ImageStatus
    evidence: list[Evidence] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    format: str | None = None

    def add_evidence(
        self,
        check: str,
        passed: bool,
        severity: str,
        message: str,
        **details: Any,
    ) -> None:
        self.evidence.append(
            Evidence(
                check=check,
                passed=passed,
                severity=severity,
                message=message,
                details=details,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["status"] = self.status.value
        return data