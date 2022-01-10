import base64
import json

from aws_lambda_powertools import Tracer, Logger

tracer = Tracer()
logger = Logger()

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):

    logger.info(event)

    for record in event['Records']:
        item = json.loads(base64.b64decode(record['kinesis']['data']))

        # Return and report the failed record as soon as we encounter a problem
        if 'error' in item['id']:
            logger.error(item)
            return {"batchItemFailures":[{"itemIdentifier": record["kinesis"]["sequenceNumber"]}]}

    return
