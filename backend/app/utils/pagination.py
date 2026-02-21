"""Pagination helpers"""
from dataclasses import dataclass
from typing import Any

from fastapi import Query


@dataclass
class PaginationParams:
    page: int
    per_page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


def pagination_params(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)
