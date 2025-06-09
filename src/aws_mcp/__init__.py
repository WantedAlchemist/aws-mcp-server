"""AWS MCP Server - Model Context Protocol server for AWS API integration."""

from .server import AWSMCPServer
from .client import AWSClient
from .config import AWSConfig, AccountConfig, RegionConfig, CostConfig
from .exceptions import AWSError, AuthenticationError, ResourceNotFoundError

__version__ = "0.1.0"

__all__ = [
    "AWSMCPServer",
    "AWSClient",
    "AWSConfig",
    "AccountConfig",
    "RegionConfig",
    "CostConfig",
    "AWSError",
    "AuthenticationError",
    "ResourceNotFoundError",
]