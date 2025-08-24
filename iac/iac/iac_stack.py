import os
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
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
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("../src"),
            environment={"STAGE":"TEST"},
            handler="app.main.handler",
            timeout=Duration.seconds(15),
        )

        api = apigateway.LambdaRestApi(
            self,
            "SimpleApiGateway",
            handler=lambda_fn,
            proxy=True,
            description="API Gateway for Lambda handler"
        )



               
        

