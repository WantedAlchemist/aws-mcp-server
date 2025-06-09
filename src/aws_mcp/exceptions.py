"""Custom exceptions for AWS MCP Server."""

from typing import Optional, Dict, Any


class AWSError(Exception):
    """Base exception for AWS-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details or {}


class AuthenticationError(AWSError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str, auth_type: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="AuthenticationFailed",
            status_code=401
        )
        self.auth_type = auth_type


class AuthorizationError(AWSError):
    """Raised when user lacks permissions."""
    
    def __init__(self, message: str, action: Optional[str] = None, resource: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="AccessDenied",
            status_code=403
        )
        self.action = action
        self.resource = resource


class ResourceNotFoundError(AWSError):
    """Raised when a requested resource doesn't exist."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="ResourceNotFound",
            status_code=404
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(AWSError):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        message: str,
        parameter: Optional[str] = None,
        value: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            error_code="ValidationError",
            status_code=400
        )
        self.parameter = parameter
        self.value = value


class LimitExceededError(AWSError):
    """Raised when an AWS service limit is exceeded."""
    
    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        current_value: Optional[int] = None,
        limit_value: Optional[int] = None
    ):
        super().__init__(
            message=message,
            error_code="LimitExceeded",
            status_code=429
        )
        self.limit_type = limit_type
        self.current_value = current_value
        self.limit_value = limit_value


class ThrottlingError(AWSError):
    """Raised when API requests are throttled."""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            error_code="Throttling",
            status_code=429
        )
        self.retry_after = retry_after


class ServiceError(AWSError):
    """Raised when an AWS service encounters an error."""
    
    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="ServiceError",
            status_code=500
        )
        self.service = service
        self.operation = operation


class CostLimitError(AWSError):
    """Raised when cost limits are exceeded."""
    
    def __init__(
        self,
        message: str,
        estimated_cost: Optional[float] = None,
        limit: Optional[float] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="CostLimitExceeded",
            status_code=403
        )
        self.estimated_cost = estimated_cost
        self.limit = limit
        self.operation = operation


class RegionNotEnabledError(AWSError):
    """Raised when trying to access a non-enabled region."""
    
    def __init__(
        self,
        message: str,
        region: Optional[str] = None,
        enabled_regions: Optional[list] = None
    ):
        super().__init__(
            message=message,
            error_code="RegionNotEnabled",
            status_code=400
        )
        self.region = region
        self.enabled_regions = enabled_regions or []