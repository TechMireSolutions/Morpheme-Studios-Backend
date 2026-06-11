"""Project-wide pagination (referenced by REST_FRAMEWORK in settings)."""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DefaultPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data) -> Response:
        return Response(
            {
                "results": data,
                "pagination": {
                    "count": self.page.paginator.count,
                    "num_pages": self.page.paginator.num_pages,
                    "page": self.page.number,
                    "page_size": self.get_page_size(self.request),
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
            }
        )
