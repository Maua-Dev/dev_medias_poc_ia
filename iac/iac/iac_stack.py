import os
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_iam as iam,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

from aws_cdk import aws_apigateway as apigateway


class IacStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.project_name = os.environ.get("PROJECT_NAME")
        self.aws_account_id = os.environ.get("AWS_ACCOUNT_ID")

        # Create S3 bucket for raw data storage
        raw_data_bucket = s3.Bucket(
            self,
            "RawDataBucket",
            bucket_name=f"{self.project_name.lower()}-raw-data-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Create S3 bucket for processed data
        processed_data_bucket = s3.Bucket(
            self,
            "ProcessedDataBucket",
            bucket_name=f"{self.project_name.lower()}-processed-data-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Create Lambda function for file upload (uploads to raw data bucket)
        file_upload_fn = _lambda.Function(
            self,
            "FileUploadLambda",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("../src"),
            environment={
                "STAGE": "TEST",
                "BUCKET_NAME": raw_data_bucket.bucket_name
            },
            handler="app.file_upload_handler.upload_base64_file_handler",
            timeout=Duration.seconds(30),
        )

        # Create Lambda function for file processing (triggered by S3 events)
        file_processor_fn = _lambda.Function(
            self,
            "FileProcessorLambda",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("../src"),
            environment={
                "STAGE": "TEST",
                "RAW_BUCKET": raw_data_bucket.bucket_name,
                "PROCESSED_BUCKET": processed_data_bucket.bucket_name
            },
            handler="app.file_processor.process_file_handler",
            timeout=Duration.seconds(180),  # Increased timeout for LLM processing
        )

        # Create IAM policy for Bedrock access
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            resources=[
                f"arn:aws:bedrock:us-east-1:{self.aws_account_id}:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            ]
        )
        
        # Add Bedrock permissions to the file processor Lambda
        file_processor_fn.add_to_role_policy(bedrock_policy)

        # Grant S3 permissions
        raw_data_bucket.grant_write(file_upload_fn)
        raw_data_bucket.grant_read_write(file_processor_fn)
        processed_data_bucket.grant_write(file_processor_fn)

        # Add explicit S3 permissions for file upload Lambda (additional permissions)
        file_upload_s3_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:GetObject"
            ],
            resources=[
                f"{raw_data_bucket.bucket_arn}/*"
            ]
        )
        file_upload_fn.add_to_role_policy(file_upload_s3_policy)

        # Add S3 event notification to trigger file processor
        raw_data_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(file_processor_fn)
        )

        # Create API Gateway for file upload with only POST method
        file_upload_api = apigateway.RestApi(
            self,
            "FileUploadApiGateway",
            description="API Gateway for file upload Lambda",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["*"],
                allow_methods=["POST"],
                allow_headers=["Content-Type"]
            )
        )

        # Create the upload resource and POST method
        upload_resource = file_upload_api.root.add_resource("upload")
        upload_integration = apigateway.LambdaIntegration(file_upload_fn)
        upload_resource.add_method("POST", upload_integration)

        # Output file upload API Gateway URL
        CfnOutput(
            self,
            "FileUploadApiUrl",
            value=f"{file_upload_api.url}upload",
            description="File Upload API Gateway URL (POST /upload)"
        )

        # Output S3 bucket names
        CfnOutput(
            self,
            "RawDataBucketName",
            value=raw_data_bucket.bucket_name,
            description="S3 Bucket for raw data uploads"
        )

        CfnOutput(
            self,
            "ProcessedDataBucketName",
            value=processed_data_bucket.bucket_name,
            description="S3 Bucket for processed data"
        )

