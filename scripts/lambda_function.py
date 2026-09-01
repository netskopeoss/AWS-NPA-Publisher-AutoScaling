import json
import base64
import boto3
import gzip
import os
import urllib3

http = urllib3.PoolManager()

sns_client = boto3.client('sns')
sns_topic_arn = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    compressed_payload = base64.b64decode(event['awslogs']['data'])
    uncompressed_payload = gzip.decompress(compressed_payload)
    payload = json.loads(uncompressed_payload)

    print("Uncompressed Payload: ", json.dumps(payload, indent=2))

    for log_event in payload['logEvents']:
        try:
            message_data = json.loads(log_event['message'])
            post_message_to_api(message_data)
        except Exception as e:
            print(f"Error processing log event: {e}")
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='Lambda Error',
                Message=f"Error processing log event: {str(e)}"
            )


def post_message_to_api(message_data):
    api_url = os.environ['API_ENDPOINT']
    headers = {'Content-Type': 'application/json'}

    encoded_data = json.dumps(message_data).encode('utf-8')

    try:
        response = http.request(
            'POST',
            api_url,
            body=encoded_data,
            headers=headers
        )
        print(f"Response status: {response.status}")
        if response.status != 200:
            raise Exception(f"Non-200 response: {response.status}")
    except Exception as e:
        print(f"Error sending data to API: {e}")
        raise
