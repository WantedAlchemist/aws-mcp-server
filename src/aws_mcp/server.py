"""AWS MCP Server implementation."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Sequence
from datetime import datetime

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
except ImportError:
    # Use mock for testing
    from salesforce_mcp.mcp_mock import Server, NotificationOptions, InitializationOptions, stdio_server, Tool, TextContent
    
    class types:
        Tool = Tool
        TextContent = TextContent
        ImageContent = None
        EmbeddedResource = None
    
    class mcp:
        class server:
            stdio = type('stdio', (), {'stdio_server': stdio_server})

from .client import AWSClient
from .config import AWSConfig, AccountConfig
from .exceptions import AWSError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AWSMCPServer:
    """MCP Server for AWS API integration."""
    
    def __init__(
        self,
        config: Optional[AWSConfig] = None,
        accounts: Optional[Dict[str, AccountConfig]] = None,
        default_account: str = "default"
    ):
        self.server = Server("aws-mcp")
        self.config = config or AWSConfig()
        self.accounts = accounts or {"default": self.config.get_account_config()}
        self.default_account = default_account
        self.clients: Dict[str, AWSClient] = {}
        
        # Register handlers
        self._register_handlers()
        
        # Audit log setup
        self.audit_log_enabled = self.config.enable_audit_log
        self.audit_log_file = self.config.audit_log_file
    
    def _register_handlers(self):
        """Register all tool handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """Return list of available tools."""
            return [
                # EC2 Tools
                types.Tool(
                    name="aws_ec2_list_instances",
                    description="List EC2 instances",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filters": {"type": "array", "items": {"type": "object"}, "description": "Instance filters"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        }
                    }
                ),
                types.Tool(
                    name="aws_ec2_create_instance",
                    description="Create a new EC2 instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ami_id": {"type": "string", "description": "AMI ID"},
                            "instance_type": {"type": "string", "description": "Instance type"},
                            "key_name": {"type": "string", "description": "Key pair name"},
                            "security_group_ids": {"type": "array", "items": {"type": "string"}},
                            "subnet_id": {"type": "string", "description": "Subnet ID"},
                            "tags": {"type": "object", "description": "Instance tags"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["ami_id", "instance_type"]
                    }
                ),
                types.Tool(
                    name="aws_ec2_stop_instance",
                    description="Stop an EC2 instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {"type": "string", "description": "Instance ID"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["instance_id"]
                    }
                ),
                types.Tool(
                    name="aws_ec2_start_instance",
                    description="Start an EC2 instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {"type": "string", "description": "Instance ID"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["instance_id"]
                    }
                ),
                # S3 Tools
                types.Tool(
                    name="aws_s3_list_buckets",
                    description="List S3 buckets",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "account": {"type": "string", "description": "Target account name"}
                        }
                    }
                ),
                types.Tool(
                    name="aws_s3_list_objects",
                    description="List objects in S3 bucket",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name"},
                            "prefix": {"type": "string", "description": "Object prefix"},
                            "max_keys": {"type": "integer", "description": "Maximum number of keys", "default": 1000},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["bucket"]
                    }
                ),
                types.Tool(
                    name="aws_s3_upload_object",
                    description="Upload object to S3",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name"},
                            "key": {"type": "string", "description": "Object key"},
                            "content": {"type": "string", "description": "Object content"},
                            "content_type": {"type": "string", "description": "Content type"},
                            "metadata": {"type": "object", "description": "Object metadata"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["bucket", "key", "content"]
                    }
                ),
                types.Tool(
                    name="aws_s3_presigned_url",
                    description="Generate presigned URL for S3 object",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string", "description": "Bucket name"},
                            "key": {"type": "string", "description": "Object key"},
                            "operation": {"type": "string", "description": "Operation", "default": "get_object"},
                            "expiration": {"type": "integer", "description": "URL expiration in seconds", "default": 3600},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["bucket", "key"]
                    }
                ),
                # Lambda Tools
                types.Tool(
                    name="aws_lambda_invoke",
                    description="Invoke Lambda function",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "function_name": {"type": "string", "description": "Function name or ARN"},
                            "payload": {"type": "object", "description": "Function payload"},
                            "invocation_type": {"type": "string", "description": "Invocation type", "default": "RequestResponse"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["function_name"]
                    }
                ),
                types.Tool(
                    name="aws_lambda_list_functions",
                    description="List Lambda functions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        }
                    }
                ),
                # DynamoDB Tools
                types.Tool(
                    name="aws_dynamodb_query",
                    description="Query DynamoDB table",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string", "description": "Table name"},
                            "key_condition_expression": {"type": "string", "description": "Key condition expression"},
                            "expression_attribute_values": {"type": "object", "description": "Expression attribute values"},
                            "expression_attribute_names": {"type": "object", "description": "Expression attribute names"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["table_name", "key_condition_expression", "expression_attribute_values"]
                    }
                ),
                # CloudFormation Tools
                types.Tool(
                    name="aws_cloudformation_create_stack",
                    description="Create CloudFormation stack",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stack_name": {"type": "string", "description": "Stack name"},
                            "template_body": {"type": "string", "description": "Template body"},
                            "template_url": {"type": "string", "description": "Template URL"},
                            "parameters": {"type": "array", "items": {"type": "object"}, "description": "Stack parameters"},
                            "capabilities": {"type": "array", "items": {"type": "string"}, "description": "Required capabilities"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["stack_name"]
                    }
                ),
                types.Tool(
                    name="aws_cloudformation_describe_stack",
                    description="Describe CloudFormation stack",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stack_name": {"type": "string", "description": "Stack name"},
                            "region": {"type": "string", "description": "AWS region"},
                            "account": {"type": "string", "description": "Target account name"}
                        },
                        "required": ["stack_name"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str,
            arguments: Optional[Dict[str, Any]] = None
        ) -> Sequence[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            """Handle tool execution."""
            try:
                # Log the tool call
                await self._audit_log("tool_call", {
                    "tool": name,
                    "arguments": arguments,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Get the appropriate client
                account_name = arguments.get("account", self.default_account) if arguments else self.default_account
                client = await self._get_client(account_name)
                
                # Execute the tool
                result = await self._execute_tool(name, arguments or {}, client)
                
                # Log success
                await self._audit_log("tool_success", {
                    "tool": name,
                    "account": account_name,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]
                
            except AWSError as e:
                # Log error
                await self._audit_log("tool_error", {
                    "tool": name,
                    "error": str(e),
                    "error_code": e.error_code,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                error_response = {
                    "error": e.message,
                    "error_code": e.error_code,
                    "request_id": e.request_id,
                    "details": e.details
                }
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(error_response, indent=2)
                )]
            
            except Exception as e:
                logger.exception(f"Unexpected error in tool {name}")
                error_response = {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(error_response, indent=2)
                )]
    
    async def _get_client(self, account_name: str) -> AWSClient:
        """Get or create a client for the specified account."""
        if account_name not in self.clients:
            if account_name not in self.accounts:
                # Try to load from environment
                account_config = self.config.get_account_config(account_name)
                if not account_config.access_key_id and not account_config.role_arn and not account_config.profile:
                    raise ValueError(f"Unknown account: {account_name}")
                self.accounts[account_name] = account_config
            
            self.clients[account_name] = AWSClient(
                self.accounts[account_name],
                self.config.get_region_config(),
                self.config.get_cost_config()
            )
        
        return self.clients[account_name]
    
    async def _execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        client: AWSClient
    ) -> Dict[str, Any]:
        """Execute a specific tool."""
        # Remove account from arguments as it's not needed by the client methods
        arguments = {k: v for k, v in arguments.items() if k != "account"}
        
        # EC2 operations
        if name == "aws_ec2_list_instances":
            return {"instances": client.list_instances(**arguments)}
        
        elif name == "aws_ec2_create_instance":
            result = client.create_instance(**arguments)
            return {"success": True, "instance": result}
        
        elif name == "aws_ec2_stop_instance":
            ec2 = client.get_client('ec2', arguments.get('region'))
            response = ec2.stop_instances(InstanceIds=[arguments['instance_id']])
            return {"success": True, "state": response['StoppingInstances'][0]['CurrentState']['Name']}
        
        elif name == "aws_ec2_start_instance":
            ec2 = client.get_client('ec2', arguments.get('region'))
            response = ec2.start_instances(InstanceIds=[arguments['instance_id']])
            return {"success": True, "state": response['StartingInstances'][0]['CurrentState']['Name']}
        
        # S3 operations
        elif name == "aws_s3_list_buckets":
            return {"buckets": client.list_buckets()}
        
        elif name == "aws_s3_list_objects":
            s3 = client.get_client('s3')
            kwargs = {
                'Bucket': arguments['bucket'],
                'MaxKeys': arguments.get('max_keys', 1000)
            }
            if 'prefix' in arguments:
                kwargs['Prefix'] = arguments['prefix']
            
            response = s3.list_objects_v2(**kwargs)
            objects = [{
                'Key': obj['Key'],
                'Size': obj['Size'],
                'LastModified': obj['LastModified'].isoformat()
            } for obj in response.get('Contents', [])]
            
            return {"objects": objects, "count": len(objects)}
        
        elif name == "aws_s3_upload_object":
            result = client.upload_object(**arguments)
            return {"success": True, "object": result}
        
        elif name == "aws_s3_presigned_url":
            url = client.generate_presigned_url(**arguments)
            return {"url": url, "expiration": arguments.get('expiration', 3600)}
        
        # Lambda operations
        elif name == "aws_lambda_invoke":
            result = await client.invoke_lambda(**arguments)
            return {"success": True, "result": result}
        
        elif name == "aws_lambda_list_functions":
            lambda_client = client.get_client('lambda', arguments.get('region'))
            response = lambda_client.list_functions()
            functions = [{
                'FunctionName': func['FunctionName'],
                'Runtime': func['Runtime'],
                'Handler': func['Handler'],
                'LastModified': func['LastModified']
            } for func in response['Functions']]
            return {"functions": functions}
        
        # DynamoDB operations
        elif name == "aws_dynamodb_query":
            items = client.query_table(**arguments)
            return {"items": items, "count": len(items)}
        
        # CloudFormation operations
        elif name == "aws_cloudformation_create_stack":
            cf = client.get_client('cloudformation', arguments.get('region'))
            kwargs = {'StackName': arguments['stack_name']}
            
            if 'template_body' in arguments:
                kwargs['TemplateBody'] = arguments['template_body']
            elif 'template_url' in arguments:
                kwargs['TemplateURL'] = arguments['template_url']
            
            if 'parameters' in arguments:
                kwargs['Parameters'] = arguments['parameters']
            if 'capabilities' in arguments:
                kwargs['Capabilities'] = arguments['capabilities']
            
            response = cf.create_stack(**kwargs)
            return {"success": True, "stack_id": response['StackId']}
        
        elif name == "aws_cloudformation_describe_stack":
            cf = client.get_client('cloudformation', arguments.get('region'))
            response = cf.describe_stacks(StackName=arguments['stack_name'])
            
            if response['Stacks']:
                stack = response['Stacks'][0]
                return {
                    "stack_name": stack['StackName'],
                    "status": stack['StackStatus'],
                    "creation_time": stack['CreationTime'].isoformat(),
                    "description": stack.get('Description', ''),
                    "outputs": stack.get('Outputs', [])
                }
            
            return {"error": "Stack not found"}
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    async def _audit_log(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log audit events."""
        if not self.audit_log_enabled:
            return
        
        log_entry = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        if self.audit_log_file:
            try:
                with open(self.audit_log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")
        else:
            logger.info(f"Audit: {json.dumps(log_entry)}")
    
    async def run(self):
        """Run the MCP server."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="aws-mcp",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )


def main():
    """Main entry point."""
    import sys
    
    try:
        # Load configuration
        config = AWSConfig()
        config.validate_config()
        
        # Create and run server
        server = AWSMCPServer(config)
        asyncio.run(server.run())
        
    except Exception as e:
        logger.exception("Failed to start AWS MCP Server")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()