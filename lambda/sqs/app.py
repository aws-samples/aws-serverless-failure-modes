import json

from aws_lambda_powertools import Tracer, Logger

tracer = Tracer()
logger = Logger()

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    logger.info(event)

    batch_failures = []
    batch_ids = []

    for record in event['Records']:
        message_body = json.loads(record['body'])
        batch_ids.append(message_body['id'])

        # Unlike Kinesis and Dynamo lambdas, we continue here as we can report on all failed messages
        if 'error' in message_body['id']:
            batch_failures.append({"itemIdentifier": record["messageId"]})
            continue

    logger.debug(batch_ids)

    return {"batchItemFailures": batch_failures}