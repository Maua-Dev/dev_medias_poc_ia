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

        lambda_fn = _lambda.Function(
            self,
            "SimpleFastAPILambda",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("../src"),
            environment={"STAGE":"TEST"},
            handler="app.main.lambda_handler",
            timeout=Duration.seconds(15),
        )

        # Create S3 bucket for file storage
        file_bucket = s3.Bucket(
            self,
            f"{self.project_name}UploadBucket",
            bucket_name=f"{self.project_name.lower()}uploadbucket",
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

        api = apigateway.LambdaRestApi(
            self,
            "SimpleApiGateway",
            handler=lambda_fn,
            proxy=True,
            description="API Gateway for Lambda handler"
        )

        # Create API Gateway for file upload
        file_upload_api = apigateway.LambdaRestApi(
            self,
            "FileUploadApiGateway",
            handler=file_upload_fn,
            proxy=True,
            description="API Gateway for file upload Lambda"
        )


               
        

