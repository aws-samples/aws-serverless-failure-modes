import os
import uuid
import json
import boto3

from aws_lambda_powertools import Tracer, Metrics, Logger
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver
from aws_lambda_powertools.event_handler.exceptions import (ServiceError)

tracer = Tracer()
metrics = Metrics()
metrics.set_default_dimensions(environment=os.environ['ENVIRONMENT_NAME'])
logger = Logger()
app = ApiGatewayResolver()  # by default API Gateway REST API (v1)

dynamodb = boto3.resource('dynamodb')
sqs = boto3.resource('sqs')
events = boto3.client('events')
kinesis = boto3.client('kinesis')
dynamo_table = dynamodb.Table(os.environ['DYNAMO_TABLE'])
sqs_queue = sqs.Queue(os.environ['SQS_QUEUE_URL'])

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    return app.resolve(event, context)


@app.get("/error")
@tracer.capture_method
def get_error():
    # Illustrates capturing an error and re-raising with something sensible for the end client
    try:
        raise Exception("Demo error")
    except Exception as e:
        logger.error(e)
        metrics.add_metric(name='API_Error_Simulated',
                           unit=MetricUnit.Count, value=1)
        raise ServiceError(502, "Something went wrong! Please try again.")


@app.post("/dynamo")
@tracer.capture_method
def post_dynamo():
    try:
        body = app.current_event.json_body

        if 'id' not in body:
            body['id'] = str(uuid.uuid4())

        dynamo_table.put_item(Item=body)

        return {"result": body['id']}
    except Exception as e:
        logger.error(e)
        metrics.add_metric(name='API_Error_Dynamo',
                           unit=MetricUnit.Count, value=1)
        raise ServiceError(502, "Something went wrong! Please try again.")


@app.post("/sqs")
@tracer.capture_method
def post_sqs():
    try:
        body = app.current_event.json_body

        if 'id' not in body:
            body['id'] = str(uuid.uuid4())

        sqs_queue.send_message(MessageBody=json.dumps(body))

        return {"result": body['id']}
    except Exception as e:
        logger.error(e)
        metrics.add_metric(name='API_Error_SQS',
                           unit=MetricUnit.Count, value=1)
        raise ServiceError(502, "Something went wrong! Please try again.")


@app.post("/events")
@tracer.capture_method
def post_events():
    try:
        event = app.current_event.json_body

        if 'id' not in event:
            event['id'] = str(uuid.uuid4())

        events.put_events(Entries=[{
            'Source': 'events-api',
            'DetailType': 'NewItem',
            'Detail': json.dumps(event),
            'EventBusName': os.environ['EVENT_BUS_NAME']
        }])

        return {"result": event['id']}
    except Exception as e:
        logger.error(e)
        metrics.add_metric(name='API_Error_Events',
                           unit=MetricUnit.Count, value=1)
        raise ServiceError(502, "Something went wrong! Please try again.")


@app.post("/kinesis")
@tracer.capture_method
def post_kinesis():
    try:
        body = app.current_event.json_body
        if 'id' not in body:
            body['id'] = str(uuid.uuid4())

        kinesis.put_record(
            StreamName=os.environ['KINESIS_STREAM_NAME'],
            Data=json.dumps(body),
            PartitionKey=body['id']
        )

        return {"result": body['id']}
    except Exception as e:
        logger.error(e)
        metrics.add_metric(name='API_Error_Kinesis',
                           unit=MetricUnit.Count, value=1)
        raise ServiceError(502, "Something went wrong! Please try again.")
