"""Configuration management for AWS MCP Server."""

from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings
import os


class CostConfig(BaseModel):
    """Cost tracking and optimization configuration."""
    
    track_costs: bool = Field(default=True, description="Enable cost tracking")
    cost_alert_threshold: float = Field(default=100.0, description="Alert threshold in USD")
    require_cost_approval: bool = Field(default=False, description="Require approval for expensive operations")
    cost_allocation_tags: List[str] = Field(default_factory=list, description="Tags for cost allocation")
    daily_budget_limit: Optional[float] = Field(default=None, description="Daily spending limit in USD")


class RegionConfig(BaseModel):
    """Region-specific configuration."""
    
    enabled_regions: List[str] = Field(
        default_factory=lambda: ["us-east-1", "us-west-2"],
        description="List of enabled AWS regions"
    )
    default_region: str = Field(default="us-east-1", description="Default AWS region")
    region_failover: bool = Field(default=True, description="Enable automatic region failover")


class AccountConfig(BaseModel):
    """Configuration for a single AWS account."""
    
    access_key_id: Optional[str] = Field(default=None, description="AWS access key ID")
    secret_access_key: Optional[SecretStr] = Field(default=None, description="AWS secret access key")
    session_token: Optional[SecretStr] = Field(default=None, description="AWS session token")
    
    role_arn: Optional[str] = Field(default=None, description="IAM role ARN to assume")
    role_session_name: Optional[str] = Field(default="mcp-session", description="Role session name")
    external_id: Optional[str] = Field(default=None, description="External ID for role assumption")
    
    region: str = Field(default="us-east-1", description="AWS region")
    profile: Optional[str] = Field(default=None, description="AWS profile name")
    
    mfa_serial: Optional[str] = Field(default=None, description="MFA device serial number")
    
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    
    class Config:
        json_encoders = {SecretStr: lambda v: v.get_secret_value() if v else None}


class AWSConfig(BaseSettings):
    """Main configuration for AWS MCP Server."""
    
    # Default account settings
    access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    secret_access_key: Optional[SecretStr] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    session_token: Optional[SecretStr] = Field(default=None, env="AWS_SESSION_TOKEN")
    
    # Role assumption
    role_arn: Optional[str] = Field(default=None, env="AWS_ROLE_ARN")
    role_session_name: str = Field(default="mcp-session", env="AWS_ROLE_SESSION_NAME")
    external_id: Optional[str] = Field(default=None, env="AWS_EXTERNAL_ID")
    
    # Region settings
    default_region: str = Field(default="us-east-1", env="AWS_DEFAULT_REGION")
    enabled_regions: List[str] = Field(
        default_factory=lambda: ["us-east-1", "us-west-2"],
        env="AWS_ENABLED_REGIONS"
    )
    
    # Profile and MFA
    profile: Optional[str] = Field(default=None, env="AWS_PROFILE")
    mfa_serial: Optional[str] = Field(default=None, env="AWS_MFA_SERIAL")
    
    # API settings
    timeout: int = Field(default=30, env="AWS_TIMEOUT")
    max_retries: int = Field(default=3, env="AWS_MAX_RETRIES")
    
    # Server settings
    enable_audit_log: bool = Field(default=True, env="AWS_ENABLE_AUDIT_LOG")
    audit_log_file: Optional[str] = Field(default=None, env="AWS_AUDIT_LOG_FILE")
    
    # Cost tracking
    track_costs: bool = Field(default=True, env="AWS_TRACK_COSTS")
    cost_alert_threshold: float = Field(default=100.0, env="AWS_COST_ALERT_THRESHOLD")
    
    # Security
    require_mfa: bool = Field(default=False, env="AWS_REQUIRE_MFA")
    allowed_services: List[str] = Field(default_factory=list, env="AWS_ALLOWED_SERVICES")
    blocked_actions: List[str] = Field(default_factory=list, env="AWS_BLOCKED_ACTIONS")
    
    # Multi-account support
    default_account: str = Field(default="default", env="AWS_DEFAULT_ACCOUNT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_account_config(self, account_name: Optional[str] = None) -> AccountConfig:
        """Get configuration for a specific account."""
        if account_name and account_name != "default":
            # Look for account-specific environment variables
            prefix = f"AWS_{account_name.upper()}_"
            account_config = AccountConfig(
                access_key_id=os.getenv(f"{prefix}ACCESS_KEY_ID", self.access_key_id),
                secret_access_key=SecretStr(os.getenv(f"{prefix}SECRET_ACCESS_KEY", 
                    self.secret_access_key.get_secret_value() if self.secret_access_key else "")),
                session_token=SecretStr(os.getenv(f"{prefix}SESSION_TOKEN", 
                    self.session_token.get_secret_value() if self.session_token else "")),
                role_arn=os.getenv(f"{prefix}ROLE_ARN", self.role_arn),
                region=os.getenv(f"{prefix}REGION", self.default_region),
                profile=os.getenv(f"{prefix}PROFILE", self.profile),
                mfa_serial=os.getenv(f"{prefix}MFA_SERIAL", self.mfa_serial),
                timeout=int(os.getenv(f"{prefix}TIMEOUT", str(self.timeout))),
                max_retries=int(os.getenv(f"{prefix}MAX_RETRIES", str(self.max_retries)))
            )
        else:
            # Use default configuration
            account_config = AccountConfig(
                access_key_id=self.access_key_id,
                secret_access_key=self.secret_access_key,
                session_token=self.session_token,
                role_arn=self.role_arn,
                role_session_name=self.role_session_name,
                external_id=self.external_id,
                region=self.default_region,
                profile=self.profile,
                mfa_serial=self.mfa_serial,
                timeout=self.timeout,
                max_retries=self.max_retries
            )
        
        return account_config
    
    def get_region_config(self) -> RegionConfig:
        """Get region configuration."""
        return RegionConfig(
            enabled_regions=self.enabled_regions,
            default_region=self.default_region,
            region_failover=True
        )
    
    def get_cost_config(self) -> CostConfig:
        """Get cost tracking configuration."""
        return CostConfig(
            track_costs=self.track_costs,
            cost_alert_threshold=self.cost_alert_threshold,
            require_cost_approval=False,
            cost_allocation_tags=[]
        )
    
    def validate_config(self) -> bool:
        """Validate the configuration."""
        # Check if we have valid credentials
        has_keys = all([self.access_key_id, self.secret_access_key])
        has_role = self.role_arn is not None
        has_profile = self.profile is not None
        
        if not (has_keys or has_role or has_profile):
            raise ValueError(
                "Invalid configuration: AWS credentials required (access keys, role ARN, or profile)"
            )
        
        # Validate regions
        valid_regions = [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
            "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
            "sa-east-1", "ca-central-1", "ap-south-1", "eu-north-1"
        ]
        
        for region in self.enabled_regions:
            if region not in valid_regions:
                raise ValueError(f"Invalid region: {region}")
        
        return True