"""Host-neutral operation, cancellation, and safe-error contracts.

The shared core deliberately does not choose a thread, event loop, or UI
framework.  Hosts run these operations on their own worker facility and pass a
``CancellationToken`` through to transports that support cooperative aborts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from .prompt_templates import RenderedPrompt, ResponseMode
from .provider_requests import (
    BuiltProviderRequest,
    ChatRequestOptions,
    build_chat_completion_request,
)
from .provider_capabilities import ProviderCapabilities, ReasoningIntent


class OperationError(RuntimeError):
    """A stable, privacy-safe error suitable for crossing a host bridge."""

    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        retryable: bool = False,
        safe_details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = _safe_code(code)
        self.public_message = str(public_message).strip() or "The operation failed."
        self.retryable = bool(retryable)
        self.safe_details = _safe_details(safe_details or {})
        super().__init__(self.public_message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.public_message,
            "retryable": self.retryable,
            "details": dict(self.safe_details),
        }


class OperationCancelled(OperationError):
    def __init__(self) -> None:
        super().__init__("cancelled", "The operation was cancelled.", retryable=True)


class CancellationToken:
    """Thread-safe cooperative cancellation with optional abort callbacks."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._callbacks: list[Callable[[], None]] = []

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise OperationCancelled()

    def cancel(self) -> bool:
        """Cancel once and invoke registered abort hooks without propagating them."""
        with self._lock:
            if self._event.is_set():
                return False
            self._event.set()
            callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            try:
                callback()
            except Exception:
                # Abort hooks are best-effort and may refer to an already
                # closed socket/window.  Their exceptions contain no useful
                # application result and must not replace cancellation.
                pass
        return True

    def add_cancel_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register an abort hook and return a function that unregisters it."""
        if not callable(callback):
            raise TypeError("cancellation callback must be callable")
        with self._lock:
            if self._event.is_set():
                call_now = True
            else:
                call_now = False
                self._callbacks.append(callback)
        if call_now:
            try:
                callback()
            except Exception:
                pass

        def remove() -> None:
            with self._lock:
                try:
                    self._callbacks.remove(callback)
                except ValueError:
                    pass

        return remove


@dataclass(frozen=True, slots=True)
class OperationContext:
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    cancellation: CancellationToken = field(default_factory=CancellationToken)

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id is required")


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """Minimal transport result; raw response content is intentionally opaque."""

    content: str
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ModelRequestSettings:
    """Provider-neutral settings used by shared application services."""

    model: str
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    reasoning: ReasoningIntent = field(default_factory=ReasoningIntent)
    use_native_structured_output: bool = False
    extra_body: Mapping[str, Any] = field(default_factory=dict)

    def build(
        self,
        capabilities: ProviderCapabilities,
        prompt: RenderedPrompt,
    ) -> BuiltProviderRequest:
        response_format = None
        if self.use_native_structured_output and prompt.response_mode is ResponseMode.STRUCTURED:
            response_format = {"type": "json_object"}
        return build_chat_completion_request(
            capabilities,
            ChatRequestOptions(
                model=self.model,
                messages=prompt.messages,
                max_output_tokens=self.max_output_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                response_format=response_format,
                extra_body=self.extra_body,
            ),
            self.reasoning,
        )


class CompletionTransport(Protocol):
    def complete(
        self,
        request: BuiltProviderRequest,
        *,
        cancellation: CancellationToken,
    ) -> ModelResponse: ...


def run_completion(
    transport: CompletionTransport,
    request: BuiltProviderRequest,
    context: OperationContext,
) -> ModelResponse:
    """Run a transport with cancellation and redact all unknown failures."""
    context.cancellation.raise_if_cancelled()
    try:
        response = transport.complete(request, cancellation=context.cancellation)
    except OperationError:
        raise
    except (TimeoutError, ConnectionError) as exc:
        raise OperationError(
            "provider_unavailable",
            "The AI provider did not respond. Check the connection and try again.",
            retryable=True,
        ) from exc
    except Exception as exc:
        # Provider exception text can include URLs, headers, request bodies,
        # pasted text, or raw response bodies.  Never forward it.
        raise OperationError(
            "provider_failed",
            "The AI provider request failed. Check the provider settings and try again.",
            retryable=True,
        ) from exc
    context.cancellation.raise_if_cancelled()
    if not isinstance(response, ModelResponse):
        raise OperationError("invalid_provider_response", "The AI provider returned an invalid response.")
    return response


def public_operation_error(
    exc: BaseException,
    *,
    code: str = "operation_failed",
    message: str = "The operation failed.",
    retryable: bool = False,
) -> OperationError:
    """Preserve known safe errors and redact every unknown exception."""
    if isinstance(exc, OperationError):
        return exc
    return OperationError(code, message, retryable=retryable)


def _safe_code(value: str) -> str:
    text = str(value).strip().lower().replace("-", "_")
    if not text or any(not (char.isalnum() or char == "_") for char in text):
        return "operation_failed"
    return text[:80]


def _safe_details(values: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        name = str(key)
        lowered = name.lower()
        if any(part in lowered for part in ("key", "token", "secret", "prompt", "text", "content", "translation")):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[name[:80]] = value if not isinstance(value, str) else value[:200]
    return result
