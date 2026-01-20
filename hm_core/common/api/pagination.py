from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


def paginate(request, queryset, serializer_class, *, paginator: PageNumberPagination | None = None) -> Response:
    """
    Shared pagination helper to enforce a stable contract:
      { count, next, previous, results }
    """
    p = paginator or DefaultPagination()
    page = p.paginate_queryset(queryset, request)
    if page is not None:
        ser = serializer_class(page, many=True)
        return p.get_paginated_response(ser.data)

    # If pagination is disabled for some reason, fall back to a non-paginated list.
    ser = serializer_class(queryset, many=True)
    return Response(ser.data)
