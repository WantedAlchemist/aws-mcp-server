"""AWS API client implementation."""

import asyncio
import boto3
import aioboto3
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging
from botocore.exceptions import ClientError, BotoCoreError

from .config import AccountConfig, RegionConfig, CostConfig
from .exceptions import (
    AWSError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
    ThrottlingError,
    ServiceError
)


logger = logging.getLogger(__name__)


class AWSClient:
    """Client for interacting with AWS APIs."""
    
    def __init__(
        self,
        account_config: AccountConfig,
        region_config: Optional[RegionConfig] = None,
        cost_config: Optional[CostConfig] = None
    ):
        self.account_config = account_config
        self.region_config = region_config or RegionConfig()
        self.cost_config = cost_config or CostConfig()
        self._session = None
        self._clients = {}
        self._cost_tracker = CostTracker() if self.cost_config.track_costs else None
    
    def _get_session(self) -> boto3.Session:
        """Get or create boto3 session."""
        if not self._session:
            session_kwargs = {}
            
            if self.account_config.profile:
                session_kwargs['profile_name'] = self.account_config.profile
            
            if self.account_config.access_key_id:
                session_kwargs['aws_access_key_id'] = self.account_config.access_key_id
                session_kwargs['aws_secret_access_key'] = self.account_config.secret_access_key.get_secret_value()
                
                if self.account_config.session_token:
                    session_kwargs['aws_session_token'] = self.account_config.session_token.get_secret_value()
            
            self._session = boto3.Session(**session_kwargs)
            
            # Assume role if configured
            if self.account_config.role_arn:
                sts = self._session.client('sts')
                
                assume_role_kwargs = {
                    'RoleArn': self.account_config.role_arn,
                    'RoleSessionName': self.account_config.role_session_name
                }
                
                if self.account_config.external_id:
                    assume_role_kwargs['ExternalId'] = self.account_config.external_id
                
                try:
                    response = sts.assume_role(**assume_role_kwargs)
                    credentials = response['Credentials']
                    
                    # Create new session with assumed role credentials
                    self._session = boto3.Session(
                        aws_access_key_id=credentials['AccessKeyId'],
                        aws_secret_access_key=credentials['SecretAccessKey'],
                        aws_session_token=credentials['SessionToken']
                    )
                except ClientError as e:
                    raise AuthenticationError(
                        f"Failed to assume role: {e.response['Error']['Message']}",
                        auth_type="role_assumption"
                    )
        
        return self._session
    
    def get_client(self, service: str, region: Optional[str] = None) -> Any:
        """Get boto3 client for a service."""
        region = region or self.account_config.region
        
        # Validate region
        if region not in self.region_config.enabled_regions:
            raise ValidationError(
                f"Region {region} is not enabled",
                parameter="region",
                value=region
            )
        
        key = f"{service}:{region}"
        if key not in self._clients:
            session = self._get_session()
            self._clients[key] = session.client(
                service,
                region_name=region,
                config=boto3.session.Config(
                    retries={'max_attempts': self.account_config.max_retries},
                    connect_timeout=self.account_config.timeout,
                    read_timeout=self.account_config.timeout
                )
            )
        
        return self._clients[key]
    
    async def get_async_client(self, service: str, region: Optional[str] = None):
        """Get aioboto3 client for async operations."""
        region = region or self.account_config.region
        
        session_kwargs = {}
        if self.account_config.access_key_id:
            session_kwargs['aws_access_key_id'] = self.account_config.access_key_id
            session_kwargs['aws_secret_access_key'] = self.account_config.secret_access_key.get_secret_value()
            
            if self.account_config.session_token:
                session_kwargs['aws_session_token'] = self.account_config.session_token.get_secret_value()
        
        session = aioboto3.Session(**session_kwargs)
        
        async with session.client(service, region_name=region) as client:
            yield client
    
    def _handle_client_error(self, error: ClientError, service: str, operation: str) -> None:
        """Handle boto3 client errors and raise appropriate exceptions."""
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        
        if error_code in ['UnauthorizedOperation', 'AccessDenied', 'AccessDeniedException']:
            raise AuthorizationError(
                error_message,
                action=operation,
                resource=service
            )
        elif error_code in ['InvalidUserID.NotFound', 'NoSuchEntity', 'ResourceNotFoundException']:
            raise ResourceNotFoundError(
                error_message,
                resource_type=service
            )
        elif error_code in ['ValidationException', 'InvalidParameterValue', 'InvalidParameterCombination']:
            raise ValidationError(error_message)
        elif error_code in ['Throttling', 'ThrottlingException', 'RequestLimitExceeded']:
            raise ThrottlingError(error_message)
        else:
            raise ServiceError(
                error_message,
                service=service,
                operation=operation
            )
    
    # EC2 Operations
    def list_instances(self, filters: Optional[List[Dict]] = None, region: Optional[str] = None) -> List[Dict]:
        """List EC2 instances."""
        ec2 = self.get_client('ec2', region)
        
        try:
            kwargs = {}
            if filters:
                kwargs['Filters'] = filters
            
            response = ec2.describe_instances(**kwargs)
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append({
                        'InstanceId': instance['InstanceId'],
                        'InstanceType': instance['InstanceType'],
                        'State': instance['State']['Name'],
                        'PublicIpAddress': instance.get('PublicIpAddress'),
                        'PrivateIpAddress': instance.get('PrivateIpAddress'),
                        'LaunchTime': instance['LaunchTime'].isoformat() if instance.get('LaunchTime') else None,
                        'Tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    })
            
            return instances
            
        except ClientError as e:
            self._handle_client_error(e, 'ec2', 'describe_instances')
    
    def create_instance(
        self,
        ami_id: str,
        instance_type: str,
        key_name: Optional[str] = None,
        security_group_ids: Optional[List[str]] = None,
        subnet_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create EC2 instance."""
        ec2 = self.get_client('ec2', region)
        
        # Check cost if enabled
        if self.cost_config.track_costs:
            estimated_cost = self._estimate_ec2_cost(instance_type)
            if self.cost_config.require_cost_approval and estimated_cost > self.cost_config.cost_alert_threshold:
                raise CostLimitError(
                    f"Estimated monthly cost ${estimated_cost:.2f} exceeds threshold",
                    estimated_cost=estimated_cost,
                    limit=self.cost_config.cost_alert_threshold,
                    operation="create_instance"
                )
        
        try:
            kwargs = {
                'ImageId': ami_id,
                'InstanceType': instance_type,
                'MinCount': 1,
                'MaxCount': 1
            }
            
            if key_name:
                kwargs['KeyName'] = key_name
            if security_group_ids:
                kwargs['SecurityGroupIds'] = security_group_ids
            if subnet_id:
                kwargs['SubnetId'] = subnet_id
            
            if tags:
                kwargs['TagSpecifications'] = [{
                    'ResourceType': 'instance',
                    'Tags': [{'Key': k, 'Value': v} for k, v in tags.items()]
                }]
            
            response = ec2.run_instances(**kwargs)
            instance = response['Instances'][0]
            
            return {
                'InstanceId': instance['InstanceId'],
                'State': instance['State']['Name'],
                'InstanceType': instance_type,
                'LaunchTime': datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            self._handle_client_error(e, 'ec2', 'run_instances')
    
    # S3 Operations
    def list_buckets(self) -> List[Dict[str, Any]]:
        """List S3 buckets."""
        s3 = self.get_client('s3')
        
        try:
            response = s3.list_buckets()
            
            return [{
                'Name': bucket['Name'],
                'CreationDate': bucket['CreationDate'].isoformat() if bucket.get('CreationDate') else None
            } for bucket in response['Buckets']]
            
        except ClientError as e:
            self._handle_client_error(e, 's3', 'list_buckets')
    
    def upload_object(
        self,
        bucket: str,
        key: str,
        content: Union[str, bytes],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Upload object to S3."""
        s3 = self.get_client('s3')
        
        try:
            kwargs = {
                'Bucket': bucket,
                'Key': key,
                'Body': content.encode() if isinstance(content, str) else content
            }
            
            if content_type:
                kwargs['ContentType'] = content_type
            if metadata:
                kwargs['Metadata'] = metadata
            
            response = s3.put_object(**kwargs)
            
            return {
                'Bucket': bucket,
                'Key': key,
                'ETag': response.get('ETag', '').strip('"'),
                'VersionId': response.get('VersionId')
            }
            
        except ClientError as e:
            self._handle_client_error(e, 's3', 'put_object')
    
    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        operation: str = 'get_object',
        expiration: int = 3600
    ) -> str:
        """Generate presigned URL for S3 object."""
        s3 = self.get_client('s3')
        
        try:
            url = s3.generate_presigned_url(
                ClientMethod=operation,
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            self._handle_client_error(e, 's3', 'generate_presigned_url')
    
    # Lambda Operations
    async def invoke_lambda(
        self,
        function_name: str,
        payload: Optional[Dict[str, Any]] = None,
        invocation_type: str = 'RequestResponse',
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Invoke Lambda function."""
        import json
        
        async with self.get_async_client('lambda', region) as lambda_client:
            try:
                response = await lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType=invocation_type,
                    Payload=json.dumps(payload) if payload else '{}'
                )
                
                result = {
                    'StatusCode': response['StatusCode'],
                    'ExecutedVersion': response.get('ExecutedVersion')
                }
                
                if 'Payload' in response:
                    payload_data = await response['Payload'].read()
                    result['Payload'] = json.loads(payload_data)
                
                return result
                
            except ClientError as e:
                self._handle_client_error(e, 'lambda', 'invoke')
    
    # DynamoDB Operations
    def query_table(
        self,
        table_name: str,
        key_condition_expression: str,
        expression_attribute_values: Dict[str, Any],
        expression_attribute_names: Optional[Dict[str, str]] = None,
        region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query DynamoDB table."""
        dynamodb = self.get_client('dynamodb', region)
        
        try:
            kwargs = {
                'TableName': table_name,
                'KeyConditionExpression': key_condition_expression,
                'ExpressionAttributeValues': expression_attribute_values
            }
            
            if expression_attribute_names:
                kwargs['ExpressionAttributeNames'] = expression_attribute_names
            
            response = dynamodb.query(**kwargs)
            
            return response.get('Items', [])
            
        except ClientError as e:
            self._handle_client_error(e, 'dynamodb', 'query')
    
    def _estimate_ec2_cost(self, instance_type: str) -> float:
        """Estimate monthly cost for EC2 instance type."""
        # Simplified cost estimation - in production, use AWS Pricing API
        hourly_costs = {
            't3.micro': 0.0104,
            't3.small': 0.0208,
            't3.medium': 0.0416,
            't3.large': 0.0832,
            'm5.large': 0.096,
            'm5.xlarge': 0.192,
            'c5.large': 0.085,
            'c5.xlarge': 0.17
        }
        
        hourly_cost = hourly_costs.get(instance_type, 0.1)  # Default to $0.1/hour
        return hourly_cost * 24 * 30  # Monthly cost


class CostTracker:
    """Track AWS operation costs."""
    
    def __init__(self):
        self.operations = []
        self.total_cost = 0.0
    
    def track_operation(self, service: str, operation: str, estimated_cost: float):
        """Track an operation's cost."""
        self.operations.append({
            'timestamp': datetime.utcnow(),
            'service': service,
            'operation': operation,
            'cost': estimated_cost
        })
        self.total_cost += estimated_cost
    
    def get_daily_cost(self) -> float:
        """Get today's total cost."""
        today = datetime.utcnow().date()
        daily_cost = sum(
            op['cost'] for op in self.operations
            if op['timestamp'].date() == today
        )
        return daily_cost