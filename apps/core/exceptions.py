"""Uniform error envelope for the API.

Every error response is shaped as:
    { "error": { "code": str, "message": str, "fields"?: {field: [msgs]} } }
matching the API spec §7.5.
"""
from __future__ import annotations

from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

_CODE_BY_STATUS = {
    400: "validation_error",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "unprocessable",
    429: "throttled",
}


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    code = _CODE_BY_STATUS.get(response.status_code, "error")
    data = response.data
    fields = None
    message = "Request failed."

    if isinstance(data, dict):
        if "detail" in data:
            message = str(data["detail"])
        else:
            # Serializer field errors -> fields map.
            fields = {k: v if isinstance(v, list) else [v] for k, v in data.items()}
            message = "Validation failed."
    elif isinstance(data, list):
        message = "; ".join(str(item) for item in data)

    envelope = {"error": {"code": code, "message": message}}
    if fields:
        envelope["error"]["fields"] = fields

    return Response(envelope, status=response.status_code)


def conflict_response(message: str) -> Response:
    return Response(
        {"error": {"code": "conflict", "message": message}},
        status=http_status.HTTP_409_CONFLICT,
    )
