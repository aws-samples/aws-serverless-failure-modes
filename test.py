from os import path
import uuid
import requests
import toml
import sys
import boto3

endpoint = None

def api_call(body, is_error, path):

    if is_error:
        body['id'] = str(uuid.uuid4()) + '_error'

    r = requests.post(f'{endpoint}/{path}', json=body)
    print(r.text)


def broken_api_call():
    r = requests.get(f'{endpoint}/error')
    print(r.text)


if __name__ == "__main__":

    config_name = sys.argv[1] if len(sys.argv) > 1 else 'default'

    stack_name = toml.load("samconfig.toml")[
        config_name]['deploy']['parameters']['stack_name']

    cf_client = boto3.client('cloudformation')
    response = cf_client.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]

    endpoint = [x['OutputValue']
                for x in outputs if x['OutputKey'] == 'ApiEndpoint'][0]

    # sqs
    api_call({'something': 'value'}, is_error=False, path='sqs')
    api_call({'something': 'value'}, is_error=True, path='sqs')

    # dynamo
    api_call({'something': 'value'}, is_error=False, path='dynamo')
    api_call({'something': 'value'}, is_error=True, path='dynamo')

    # kinesis
    api_call({'something': 'value'}, is_error=False, path='kinesis')
    api_call({'something': 'value'}, is_error=True, path='kinesis')

    # events
    api_call({'something': 'value'}, is_error=False, path='events')
    api_call({'something': 'value'}, is_error=True, path='events')

    # intentional endpoint that returns a custom error
    broken_api_call()

    
