import json
import boto3
import os
from urllib.parse import unquote_plus


def process_file_handler(event, context):
    """
    Lambda handler triggered by S3 events when files are uploaded to raw data bucket.
    Processes the file and moves it to the processed data bucket.
    
    This function is triggered automatically when a file is uploaded to the raw data bucket.
    """
    
    raw_bucket = os.environ.get('RAW_BUCKET')
    processed_bucket = os.environ.get('PROCESSED_BUCKET')
    
    s3 = boto3.client('s3')
    
    try:
        # Process each record in the S3 event
        for record in event['Records']:
            # Get bucket and object key from the event
            bucket_name = record['s3']['bucket']['name']
            object_key = unquote_plus(record['s3']['object']['key'])
            
            print(f"Processing file: {object_key} from bucket: {bucket_name}")
            
            # Download the file from raw bucket
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            file_content = response['Body'].read()
            
            # Here you can add your file processing logic
            # For now, we'll just copy the file with a "processed-" prefix
            processed_key = f"processed-{object_key}"
            
            # Upload the processed file to the processed bucket
            s3.put_object(
                Bucket=processed_bucket,
                Key=processed_key,
                Body=file_content,
                Metadata={
                    'original-bucket': bucket_name,
                    'original-key': object_key,
                    'processed-timestamp': str(context.aws_request_id)
                }
            )
            
            print(f"File processed and saved as: {processed_key} in bucket: {processed_bucket}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Files processed successfully',
                'processed_files': len(event['Records'])
            })
        }
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
