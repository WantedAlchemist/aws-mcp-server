# AWS MCP Server

A comprehensive Model Context Protocol (MCP) server for integrating Amazon Web Services (AWS) APIs with GenAI applications.

## Features

- **Comprehensive AWS Service Coverage**:
  - EC2: Instance management, security groups, AMIs
  - S3: Bucket operations, object management, presigned URLs
  - Lambda: Function deployment, invocation, configuration
  - DynamoDB: Table operations, queries, batch operations
  - RDS: Database instances, snapshots, parameter groups
  - CloudFormation: Stack management, template validation
  - IAM: User, role, and policy management
  - CloudWatch: Metrics, logs, alarms
  - SQS/SNS: Message queuing and notifications
  - ECS/EKS: Container and Kubernetes management
  
- **Authentication Methods**:
  - IAM Access Keys
  - IAM Roles
  - AWS SSO
  - Temporary credentials via STS
  - MFA support

- **Enterprise Features**:
  - Multi-account support
  - Cross-region operations
  - Rate limiting and retry logic
  - Cost tracking and optimization
  - Compliance and security scanning

## Installation

```bash
pip install aws-mcp-server
```

Or install from source:

```bash
git clone https://github.com/asklokesh/aws-mcp-server.git
cd aws-mcp-server
pip install -e .
```

## Configuration

Create a `.env` file or set environment variables:

```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# OR use IAM Role
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/YourRole
AWS_ROLE_SESSION_NAME=mcp-session

# Optional Settings
AWS_SESSION_TOKEN=your_session_token
AWS_MFA_SERIAL=arn:aws:iam::123456789012:mfa/user
AWS_PROFILE=default
AWS_MAX_RETRIES=3
AWS_TIMEOUT=30
```

## Quick Start

### Basic Usage

```python
from aws_mcp import AWSMCPServer

# Initialize the server
server = AWSMCPServer()

# Start the server
server.start()
```

### Claude Desktop Configuration

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "aws": {
      "command": "python",
      "args": ["-m", "aws_mcp.server"],
      "env": {
        "AWS_ACCESS_KEY_ID": "your_access_key",
        "AWS_SECRET_ACCESS_KEY": "your_secret_key",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

## Available Tools

### EC2 Operations

#### List Instances
```python
{
  "tool": "aws_ec2_list_instances",
  "arguments": {
    "filters": [
      {"Name": "instance-state-name", "Values": ["running"]}
    ],
    "region": "us-east-1"
  }
}
```

#### Create Instance
```python
{
  "tool": "aws_ec2_create_instance",
  "arguments": {
    "ami_id": "ami-0abcdef1234567890",
    "instance_type": "t3.micro",
    "key_name": "my-key-pair",
    "security_group_ids": ["sg-123456"],
    "subnet_id": "subnet-123456",
    "tags": {"Name": "MyInstance", "Environment": "Dev"}
  }
}
```

### S3 Operations

#### List Buckets
```python
{
  "tool": "aws_s3_list_buckets",
  "arguments": {}
}
```

#### Upload Object
```python
{
  "tool": "aws_s3_upload_object",
  "arguments": {
    "bucket": "my-bucket",
    "key": "path/to/object.txt",
    "content": "File content here",
    "content_type": "text/plain"
  }
}
```

#### Generate Presigned URL
```python
{
  "tool": "aws_s3_presigned_url",
  "arguments": {
    "bucket": "my-bucket",
    "key": "path/to/object.txt",
    "expiration": 3600,
    "operation": "get_object"
  }
}
```

### Lambda Operations

#### Invoke Function
```python
{
  "tool": "aws_lambda_invoke",
  "arguments": {
    "function_name": "myFunction",
    "payload": {"key": "value"},
    "invocation_type": "RequestResponse"
  }
}
```

#### Deploy Function
```python
{
  "tool": "aws_lambda_deploy",
  "arguments": {
    "function_name": "myFunction",
    "runtime": "python3.9",
    "handler": "index.handler",
    "code_zip_path": "/path/to/code.zip",
    "role_arn": "arn:aws:iam::123456789012:role/lambda-role"
  }
}
```

### DynamoDB Operations

#### Query Table
```python
{
  "tool": "aws_dynamodb_query",
  "arguments": {
    "table_name": "MyTable",
    "key_condition_expression": "PK = :pk",
    "expression_attribute_values": {":pk": "USER#123"}
  }
}
```

### CloudFormation Operations

#### Create Stack
```python
{
  "tool": "aws_cloudformation_create_stack",
  "arguments": {
    "stack_name": "my-stack",
    "template_body": "...",
    "parameters": [
      {"ParameterKey": "KeyName", "ParameterValue": "my-key"}
    ]
  }
}
```

## Advanced Configuration

### Multi-Account Support

```python
from aws_mcp import AWSMCPServer, AccountConfig

# Configure multiple accounts
accounts = {
    "production": AccountConfig(
        access_key_id="prod_key",
        secret_access_key="prod_secret",
        region="us-east-1"
    ),
    "development": AccountConfig(
        access_key_id="dev_key",
        secret_access_key="dev_secret",
        region="us-west-2"
    ),
    "staging": AccountConfig(
        role_arn="arn:aws:iam::987654321098:role/StagingRole",
        region="eu-west-1"
    )
}

server = AWSMCPServer(accounts=accounts, default_account="production")
```

### Cross-Region Operations

```python
from aws_mcp import AWSMCPServer, RegionConfig

# Enable specific regions
regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

server = AWSMCPServer(enabled_regions=regions)
```

### Cost Optimization

```python
from aws_mcp import AWSMCPServer, CostConfig

cost_config = CostConfig(
    track_costs=True,
    cost_alert_threshold=100.0,  # Alert if estimated cost > $100
    require_cost_approval=True,   # Require approval for expensive operations
    cost_allocation_tags=["Project", "Environment", "Owner"]
)

server = AWSMCPServer(cost_config=cost_config)
```

## Integration Examples

See the `examples/` directory for complete integration examples:

- `basic_usage.py` - Common AWS operations
- `multi_account.py` - Managing multiple AWS accounts
- `infrastructure_as_code.py` - CloudFormation and CDK integration
- `cost_optimization.py` - Cost tracking and optimization
- `security_scanning.py` - Security and compliance checks
- `genai_integration.py` - Integration with GenAI APIs

## Security Best Practices

1. **Never commit credentials** - Use environment variables or AWS credential files
2. **Use IAM roles when possible** - More secure than access keys
3. **Enable MFA** - For sensitive operations
4. **Implement least privilege** - Grant minimal required permissions
5. **Enable CloudTrail** - Audit all API operations
6. **Use VPC endpoints** - For private connectivity
7. **Encrypt data** - Use KMS for encryption keys

## Error Handling

The server provides detailed error information:

```python
try:
    result = server.execute_tool("aws_ec2_create_instance", {
        "ami_id": "invalid-ami"
    })
except AWSError as e:
    print(f"AWS error: {e.error_code} - {e.message}")
    print(f"Request ID: {e.request_id}")
```

## Performance Optimization

1. **Use batch operations** - For multiple similar requests
2. **Enable caching** - For frequently accessed data
3. **Implement pagination** - For large result sets
4. **Use regional endpoints** - Reduce latency
5. **Connection pooling** - Reuse HTTP connections

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## License

MIT License - see LICENSE file for details