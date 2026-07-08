from http import HTTPStatus


class AppException(Exception):
    status_code = HTTPStatus.BAD_REQUEST
    detail = "Application error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)


class MedicineNotFoundError(AppException):
    status_code = HTTPStatus.NOT_FOUND
    detail = "Medicine not found"


class LLMProviderError(AppException):
    status_code = HTTPStatus.BAD_GATEWAY
    detail = "LLM provider error"


class OpenFDAIntegrationError(AppException):
    status_code = HTTPStatus.BAD_GATEWAY
    detail = "openFDA integration error"
