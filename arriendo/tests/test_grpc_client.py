import grpc
import pytest
from fastapi import HTTPException

from app.grpc_client import _raise_grpc_error, get_grpc_stub


def test_reutiliza_stub_grpc():
    assert get_grpc_stub() is get_grpc_stub()


class FakeRpcError(grpc.RpcError):
    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code


@pytest.mark.parametrize(
    ("grpc_code", "http_status"),
    [
        (grpc.StatusCode.CANCELLED, 503),
        (grpc.StatusCode.UNKNOWN, 502),
        (grpc.StatusCode.INVALID_ARGUMENT, 400),
        (grpc.StatusCode.DEADLINE_EXCEEDED, 504),
        (grpc.StatusCode.NOT_FOUND, 404),
        (grpc.StatusCode.ALREADY_EXISTS, 409),
        (grpc.StatusCode.PERMISSION_DENIED, 502),
        (grpc.StatusCode.RESOURCE_EXHAUSTED, 503),
        (grpc.StatusCode.ABORTED, 409),
        (grpc.StatusCode.OUT_OF_RANGE, 400),
        (grpc.StatusCode.UNIMPLEMENTED, 502),
        (grpc.StatusCode.INTERNAL, 502),
        (grpc.StatusCode.UNAVAILABLE, 503),
        (grpc.StatusCode.DATA_LOSS, 502),
        (grpc.StatusCode.UNAUTHENTICATED, 502),
    ],
)
def test_mapea_codigos_grpc_a_http(grpc_code, http_status):
    with pytest.raises(HTTPException) as exc_info:
        _raise_grpc_error(FakeRpcError(grpc_code), 50, "reserve")

    assert exc_info.value.status_code == http_status


@pytest.mark.parametrize(
    ("operation", "expected_code"),
    [
        ("reserve", "INSUFFICIENT_STOCK"),
        ("release", "INVALID_STATE_TRANSITION"),
    ],
)
def test_mapea_failed_precondition_segun_operacion(operation, expected_code):
    with pytest.raises(HTTPException) as exc_info:
        _raise_grpc_error(
            FakeRpcError(grpc.StatusCode.FAILED_PRECONDITION),
            50,
            operation,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == expected_code
