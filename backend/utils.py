"""
Core Backend Utilities & Custom Exceptions
Phase-1a: Social Media CRM Backend
"""

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class CustomException(Exception):
    """Base custom exception for the application"""
    
    def __init__(self, error_code: str, message: str, status_code: int = 400):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationException(CustomException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__("AUTHENTICATION_ERROR", message, 401)


class AuthorizationException(CustomException):
    """Raised when user doesn't have permission"""
    
    def __init__(self, message: str = "You don't have permission to access this resource"):
        super().__init__("AUTHORIZATION_ERROR", message, 403)


class ResourceNotFoundException(CustomException):
    """Raised when a resource is not found"""
    
    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} with ID {resource_id} not found"
        super().__init__("RESOURCE_NOT_FOUND", message, 404)


class ValidationException(CustomException):
    """Raised when validation fails"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__("VALIDATION_ERROR", message, 422)
        self.details = details or {}


class PlatformIntegrationException(CustomException):
    """Raised when social platform API integration fails"""
    
    def __init__(self, platform: str, message: str):
        super().__init__(
            "PLATFORM_INTEGRATION_ERROR",
            f"{platform} integration error: {message}",
            500
        )


class WebhookException(CustomException):
    """Raised when webhook processing fails"""
    
    def __init__(self, message: str):
        super().__init__("WEBHOOK_ERROR", message, 400)


# ============================================================================
# VALIDATORS
# ============================================================================

import re
from typing import Optional

class Validators:
    """Common validation functions"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password: str) -> Optional[str]:
        """
        Validate password strength.
        Returns error message if invalid, None if valid.
        """
        if len(password) < 8:
            return "Password must be at least 8 characters long"
        if not re.search(r'[A-Z]', password):
            return "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return "Password must contain at least one lowercase letter"
        if not re.search(r'[0-9]', password):
            return "Password must contain at least one digit"
        if not re.search(r'[!@#$%^&*]', password):
            return "Password must contain at least one special character (!@#$%^&*)"
        return None
    
    @staticmethod
    def validate_username(username: str) -> Optional[str]:
        """Validate username format"""
        if len(username) < 3:
            return "Username must be at least 3 characters long"
        if len(username) > 50:
            return "Username must be no longer than 50 characters"
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return "Username can only contain letters, numbers, underscores, and hyphens"
        return None
    
    @staticmethod
    def validate_ticket_number(ticket_number: str) -> bool:
        """Validate ticket number format (e.g., TKT-12345)"""
        pattern = r'^TKT-\d{6}$'
        return re.match(pattern, ticket_number) is not None


# ============================================================================
# DECORATORS
# ============================================================================

from functools import wraps
from fastapi import Depends, HTTPException
from typing import Callable

def require_role(required_roles: list):
    """Decorator to require specific user roles"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user or current_user.role not in required_roles:
                raise AuthorizationException()
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def handle_exceptions(func: Callable):
    """Decorator to handle custom exceptions"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except CustomException as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal server error")
    return wrapper


# ============================================================================
# PAGINATION UTILITIES
# ============================================================================

from pydantic import BaseModel
from typing import TypeVar, Generic, List

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    data: List[T]
    total: int
    limit: int
    offset: int
    
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages"""
        return (self.total + self.limit - 1) // self.limit
    
    @property
    def current_page(self) -> int:
        """Calculate current page number"""
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1


# ============================================================================
# DATETIME UTILITIES
# ============================================================================

from datetime import datetime, timedelta
import pytz

class DateTimeUtils:
    """DateTime utility functions"""
    
    @staticmethod
    def get_current_utc() -> datetime:
        """Get current UTC time"""
        return datetime.now(pytz.UTC)
    
    @staticmethod
    def get_current_timestamp() -> int:
        """Get current Unix timestamp"""
        return int(datetime.now().timestamp())
    
    @staticmethod
    def add_days(dt: datetime, days: int) -> datetime:
        """Add days to datetime"""
        return dt + timedelta(days=days)
    
    @staticmethod
    def add_minutes(dt: datetime, minutes: int) -> datetime:
        """Add minutes to datetime"""
        return dt + timedelta(minutes=minutes)
    
    @staticmethod
    def time_ago_string(dt: datetime) -> str:
        """Convert datetime to 'time ago' string"""
        now = datetime.now(pytz.UTC) if dt.tzinfo else datetime.now()
        delta = now - dt
        
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        elif seconds < 604800:
            return f"{int(seconds / 86400)}d ago"
        else:
            return dt.strftime("%Y-%m-%d")


# ============================================================================
# STRING UTILITIES
# ============================================================================

import uuid
import string
import random

class StringUtils:
    """String utility functions"""
    
    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_ticket_number() -> str:
        """Generate a unique ticket number"""
        random_digits = ''.join(random.choices(string.digits, k=6))
        return f"TKT-{random_digits}"
    
    @staticmethod
    def generate_random_token(length: int = 32) -> str:
        """Generate a random token"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choices(characters, k=length))
    
    @staticmethod
    def truncate_text(text: str, max_length: int) -> str:
        """Truncate text to max length"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Remove potentially dangerous characters"""
        # Remove HTML tags and scripts
        dangerous_chars = ['<', '>', '"', "'", '&']
        for char in dangerous_chars:
            text = text.replace(char, '')
        return text.strip()


# ============================================================================
# LOGGING UTILITIES
# ============================================================================

import logging
import json
from pythonjsonlogger import jsonlogger

class LoggingUtils:
    """Logging configuration utilities"""
    
    @staticmethod
    def setup_json_logging(logger_name: str = "social-crm"):
        """Setup JSON structured logging"""
        logger = logging.getLogger(logger_name)
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger
    
    @staticmethod
    def log_request(logger, method: str, path: str, user_id: str = None):
        """Log API request"""
        logger.info(json.dumps({
            "event": "API_REQUEST",
            "method": method,
            "path": path,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }))
    
    @staticmethod
    def log_error(logger, error_code: str, message: str, context: dict = None):
        """Log error event"""
        log_data = {
            "event": "ERROR",
            "error_code": error_code,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        if context:
            log_data["context"] = context
        logger.error(json.dumps(log_data))
