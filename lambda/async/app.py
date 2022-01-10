from aws_lambda_powertools import Tracer, Logger

tracer = Tracer()
logger = Logger()

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    logger.info(event)

    # Failures will go to the configured Lambda Destination after retries
    if 'error' in event['detail']['id']:
        logger.error(event)
        raise Exception("Test")