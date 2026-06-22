"""Translate raw Tencent Cloud SDK exceptions into actionable error messages.

The Tencent SDK raises ``TencentCloudSDKException`` with ``code``, ``message`` and
``requestId`` attributes. We surface those plus a human hint for common codes so
the calling agent (and user) knows what to do next.
"""
from __future__ import annotations


class HaiApiError(RuntimeError):
    """A Tencent HAI API (or orchestration) call failed, with a friendly message."""


# Hints for the error codes users hit most often.
_HINTS = {
    "AuthFailure.SignatureFailure": "Check that TENCENTCLOUD_SECRET_KEY is correct.",
    "AuthFailure.SecretIdNotFound": "Check TENCENTCLOUD_SECRET_ID and that the API key is enabled.",
    "UnauthorizedOperation": "The API key lacks HAI permissions — grant the HAI policy in CAM.",
    "ResourceInsufficient": "No capacity for that BundleType/region now. Try another bundle or region.",
    "ResourcesSoldOut": "That GPU package is sold out. Try another BundleType or region.",
    "InvalidParameterValue": "A parameter is invalid — re-check ApplicationId / BundleType / disk size.",
    "LimitExceeded": "Account limit hit (e.g. max instances). Terminate unused instances or raise the quota.",
}


def to_friendly_error(exc: Exception, action: str) -> HaiApiError:
    """Build a :class:`HaiApiError` from any exception raised while calling ``action``."""
    code = (getattr(exc, "code", "") or "").strip()
    message = (getattr(exc, "message", "") or str(exc) or "").strip()
    request_id = (getattr(exc, "requestId", "") or "").strip()

    header = f"Tencent HAI API call '{action}' failed"
    if code:
        header += f" [{code}]"

    segments = [header]
    if message:
        segments.append(message)
    hint = _HINTS.get(code)
    if hint:
        segments.append(f"Hint: {hint}")
    if request_id:
        segments.append(f"RequestId: {request_id}")
    return HaiApiError(" | ".join(segments))
