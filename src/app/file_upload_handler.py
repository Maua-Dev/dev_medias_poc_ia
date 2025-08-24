import base64
import boto3
import os


def upload_base64_file_handler(event, context):
    """
    Lambda handler to upload a base64-encoded file to S3 bucket
    
    Expected event structure:
    {
        "file_name": "example.jpg",
        "file_data": "base64_encoded_string_here"
    }
    """
    bucket_name = os.environ.get('BUCKET_NAME')
    file_name = event.get('file_name')
    file_data = event.get('file_data')
    
    if not bucket_name or not file_name or not file_data:
        return {
            'statusCode': 400,
            'body': 'Missing bucket_name, file_name, or file_data.'
        }
    
    try:
        s3 = boto3.client('s3')
        decoded_file = base64.b64decode(file_data)
        s3.put_object(Bucket=bucket_name, Key=file_name, Body=decoded_file)
        
        return {
            'statusCode': 200,
            'body': f'File {file_name} uploaded to bucket {bucket_name} successfully.'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error uploading file: {str(e)}'
        }
