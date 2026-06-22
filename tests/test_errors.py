"""Tests for Tencent SDK error translation."""
from hai_mcp.errors import HaiApiError, to_friendly_error


class _FakeSdkError(Exception):
    """Mimics tencentcloud's TencentCloudSDKException attributes."""

    def __init__(self):
        super().__init__("boom")
        self.code = "AuthFailure.SecretIdNotFound"
        self.message = "secret id not found"
        self.requestId = "req-123"


def test_includes_action_code_message_request_id_and_hint():
    err = to_friendly_error(_FakeSdkError(), "DescribeInstances")

    assert isinstance(err, HaiApiError)
    text = str(err)
    assert "DescribeInstances" in text
    assert "AuthFailure.SecretIdNotFound" in text
    assert "secret id not found" in text
    assert "req-123" in text
    assert "Hint:" in text


def test_plain_exception_is_still_wrapped():
    err = to_friendly_error(ValueError("kaboom"), "RunInstances")

    text = str(err)
    assert "RunInstances" in text
    assert "kaboom" in text
