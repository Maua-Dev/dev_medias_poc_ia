
def lambda_handler(event, context):
	print("Lambda function executed")
	print(event)
	return {
		'statusCode': 200,
		'body': 'Hello from Lambda!'
	}
