import os

from boto3.dynamodb.types import TypeDeserializer
from aws_lambda_powertools import Tracer, Metrics, Logger
from aws_lambda_powertools.metrics import MetricUnit

deserializer = TypeDeserializer()

tracer = Tracer()
metrics = Metrics()
metrics.set_default_dimensions(environment=os.environ['ENVIRONMENT_NAME'])
logger = Logger()

metric_names = {
    'INSERT': 'NewItem',
    'MODIFY': 'UpdateItem',
    'REMOVE': 'DeleteItem'
}

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):

    logger.info(event)

    for record in event['Records']:
        event_name = record['eventName']

        metrics.add_metric(
            name=metric_names[event_name], unit=MetricUnit.Count, value=1)

        if event_name == "INSERT" or event_name == "MODIFY":
            item = {k: deserializer.deserialize(
                v) for k, v in record['dynamodb']['NewImage'].items()}
            
            # Return and report the failed record as soon as we encounter a problem
            if 'error' in item['id']:
                logger.error(item)
                return {"batchItemFailures":[{"itemIdentifier": record["dynamodb"]["SequenceNumber"]}]}

    return
