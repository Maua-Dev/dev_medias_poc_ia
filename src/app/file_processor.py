import json
import boto3
import os
from urllib.parse import unquote_plus


def process_file_handler(event, context):
    """
    Lambda handler triggered by S3 events when files are uploaded to raw data bucket.
    Processes the file using Claude Sonnet 3.5 to extract structured course data.
    
    This function is triggered automatically when a file is uploaded to the raw data bucket.
    """
    
    raw_bucket = os.environ.get('RAW_BUCKET')
    processed_bucket = os.environ.get('PROCESSED_BUCKET')
    
    s3 = boto3.client('s3')
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    
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
            
            # Try to decode the file content as text
            try:
                if object_key.lower().endswith(('.txt', '.csv', '.json')):
                    text_content = file_content.decode('utf-8')
                else:
                    # For other file types, convert to base64 for analysis
                    import base64
                    text_content = f"Base64 content: {base64.b64encode(file_content).decode('utf-8')[:1000]}..."
            except UnicodeDecodeError:
                text_content = "Binary file content that couldn't be decoded"
            
            # Call Claude Sonnet 3.5 to extract structured course data
            structured_data = extract_course_data_with_claude(bedrock, text_content, object_key)
            print(structured_data)
            
            # Create the processed file with structured data
            processed_key = f"processed-{object_key.split('.')[0]}.json"
            
            # Upload the structured data to the processed bucket
            s3.put_object(
                Bucket=processed_bucket,
                Key=processed_key,
                Body=json.dumps(structured_data, indent=2),
                ContentType='application/json',
                Metadata={
                    'original-bucket': bucket_name,
                    'original-key': object_key,
                    'processed-timestamp': str(context.aws_request_id),
                    'model-used': 'claude-3-5-sonnet',
                    'tokens-used': str(structured_data.get('token_usage', {}).get('total_tokens', 0))
                }
            )
            
            print(f"Structured data saved as: {processed_key} in bucket: {processed_bucket}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Files processed successfully with Claude Sonnet 3.5',
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


def extract_course_data_with_claude(bedrock_client, content, filename):
    """
    Use Claude Sonnet 3.5 to extract structured course data from the content
    """
    
    # Define the JSON schema for course data
    schema = {
        "type": "object",
        "properties": {
            "courses": {
                "type": "object",
                "patternProperties": {
                    "^[A-Z]{3}[0-9]{3}$": {
                        "type": "object",
                        "properties": {
                            "course": {"type": "string"},
                            "name": {"type": "string"},
                            "code": {"type": "string"},
                            "period": {"type": "string"},
                            "examWeight": {"type": "number"},
                            "assignmentWeight": {"type": "number"},
                            "exams": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "weight": {"type": "number"}
                                    },
                                    "required": ["name", "weight"]
                                }
                            },
                            "assignments": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "weight": {"type": "number"}
                                    },
                                    "required": ["name", "weight"]
                                }
                            },
                            "courses": {
                                "type": "object",
                                "patternProperties": {
                                    "^[A-Z]{3}$": {"type": "number"}
                                }
                            }
                        },
                        "required": ["course", "name", "code", "period", "examWeight", "assignmentWeight", "exams", "assignments"]
                    }
                }
            }
        },
        "required": ["courses"]
    }
    
    prompt = f"""
Analyze the following content and extract course information in the specified JSON format.

Content from file '{filename}':
{content}

Please extract course data and format it according to this JSON schema:
{json.dumps(schema, indent=2)}

Example of expected output format:
{{
  "courses": {{
    "DSG244": {{
      "course": "Design",
      "name": "Estudos e Pesquisas Mercadológicas",
      "code": "DSG244",
      "period": "S",
      "examWeight": 50,
      "assignmentWeight": 50,
      "exams": [
        {{
          "name": "P1",
          "weight": 0.5
        }},
        {{
          "name": "P2",
          "weight": 0.5
        }}
      ],
      "assignments": [
        {{
          "name": "T1",
          "weight": 0.4
        }},
        {{
          "name": "T2",
          "weight": 0.4
        }},
        {{
          "name": "T3",
          "weight": 0.2
        }}
      ],
      "courses": {{
        "DSG": 2
      }}
    }}
  }}
}}

Instructions:
1. Extract all course information from the content
2. Use course codes as keys (e.g., "DSG244")
3. Ensure exam weights and assignment weights sum to 1.0 within their respective arrays
4. If information is missing, make reasonable assumptions based on typical academic structures
5. Return only valid JSON that matches the schema

JSON Response:
"""

    try:
        # Call Claude Sonnet 3.5 using cross-region inference profile
        response = bedrock_client.invoke_model(
            modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1
            })
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        claude_response = response_body['content'][0]['text']
        
        # Log token usage information
        usage = response_body.get('usage', {})
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        total_tokens = input_tokens + output_tokens
        
        print(f"Claude API Usage - Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}")
        print(f"File: {filename} - Token cost: ${total_tokens * 0.000003:.6f}")  # Approximate cost for Claude 3.5 Sonnet
        
        # Extract JSON from Claude's response
        try:
            # Try to parse the JSON directly
            structured_data = json.loads(claude_response)
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', claude_response, re.DOTALL)
            if json_match:
                structured_data = json.loads(json_match.group())
            else:
                raise ValueError("Could not extract valid JSON from Claude's response")
        
        # Add token usage information to the structured data
        structured_data['token_usage'] = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens,
            'estimated_cost_usd': total_tokens * 0.000003
        }
        
        return structured_data
        
    except Exception as e:
        print(f"Error calling Claude: {str(e)}")
        # Return a default structure if Claude fails
        return {
            "courses": {},
            "error": f"Failed to process with Claude: {str(e)}",
            "original_content_preview": content[:500] + "..." if len(content) > 500 else content
        }
