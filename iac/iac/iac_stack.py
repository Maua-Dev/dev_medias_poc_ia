import os
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_s3 as s3,
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

        # Create S3 bucket for file storage with unique name
        import hashlib
        import time
        unique_suffix = hashlib.md5(f"{self.project_name}-{self.aws_account_id}-{str(int(time.time()))}".encode()).hexdigest()[:8]
        
        file_bucket = s3.Bucket(
            self,
            "FileUploadBucket",
            bucket_name=f"{self.project_name.lower()}-uploads-{unique_suffix}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Create Lambda function for file upload
        file_upload_fn = _lambda.Function(
            self,
            "FileUploadLambda",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("../src"),
            environment={
                "STAGE": "TEST",
                "BUCKET_NAME": file_bucket.bucket_name
            },
            handler="app.file_upload_handler.upload_base64_file_handler",
            timeout=Duration.seconds(30),
        )

        # Grant S3 permissions to the file upload Lambda
        file_bucket.grant_write(file_upload_fn)

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

        # Output S3 bucket name
        CfnOutput(
            self,
            "S3BucketName",
            value=file_bucket.bucket_name,
            description="S3 Bucket for file uploads"
        )

