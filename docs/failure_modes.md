# Table of Contents
1. [General Principles](#general-principles)  
2. [API Gateway to API Lambda](#api-gateway-to-lambda)  
3. [Kinesis To Lambda](#kinesis-to-lambda)  
4. [SQS To Lambda](#sqs-to-lambda)  
5. [Streams to Lambda](#streams-to-lambda)  
6. [Eventbridge](#eventbridge)  
7. [Async Lambda Invocations](#async-lambda-invocations)  
8. [Redriving Failed Records](#redriving-failed-records)  

## General Principles

When using serverless technologies, we are piecing together different services that often operate in similar ways at first glance. However when we dive deep into the technical detail, key differences arise that we need to be aware of. It's important to consider failure modes and error handling across your stack. Potential challenges you could encounter include excessive retries and queue processors being backed up - all of which can incur additional expense. Dealing with failure is a key element of designing new applications, and a common approach to this is to move problematic records to the side, into a dead-letter-queue (DLQ). Across the serverless landscape, numerous services have an option for this, however their implementations are not the same. It is critical to know where our DLQs belong for different patterns, and what levers we can pull to control how the system handles these problematic records. Moving such records to a DLQ enables your system to continue processing other records. It also allows you breathing room to inspect failed records and do something about it. Perhaps you have a code bug, or perhaps it was a transient error. Once the problem is remediated you can reprocess those records, if appropriate.

It is important to design your system so that it is capable of handling duplicate and retried events. This is a much easier path than trying to build a system that enforces exactly-once processing. It allows you to lean in to the retry mechanisms available and build a more resilient system. The [Lambda Operator Guide](https://docs.aws.amazon.com/lambda/latest/operatorguide/retries-failures.html) has more detail on this thinking.

All code we write involves risk, and when we deploy new code, that risk increases. Our deployments should be mindful of this and be prepared to undo any changes to our system that cause problems. For the Lambda functions in this application, we make use of SAM shorthand to create a deployment strategy for the function. When we update the function, we test our function by only sending a percentage of traffic to it for a time. Whilst this is happening, we track CloudWatch Alarms, which if triggered, cancels the deployment and returns all traffic to the previous version. 

## API Gateway to Lambda

There are two key elements to consider in this pattern. First is instrumenting our client to handle API errors in an appropriate manner. Secondly we need to ensure our Lambda code reports errors in a useful way. 

Even if your function code is error-free, the client will still experience errors. Note that the API Gateway SLA of 99.95% uptime equates to up to 43s of downtime per day, or 21m 54s per month. It is essential to account for this in your client code and ensure failure is handled gracefully for your end users.

Within our Lambda code, we should try to capture all errors and ensure an appropriate error is returned to the client. Unhandled errors in our API function will be returned to the caller with a HTTP code 502 and the following:

`{"message": "Internal server error"}`

This is not a useful message for a client. Was this a temporary issue that the client should retry? Was the request malformed? We want to capture all errors and return clear information to clients. When capturing errors we should log them out for further inspection. We do not use a DLQ in this pattern - the Lambda function is invoked synchronously and the response returned to the client. It would not make sense to put records in a dead-letter-queue, because if you replayed the event you would have no mechanism of communicating any result to the requestor. By Logging errors and monitoring alarms - this gives us the information we need to make changes to our system so that future API calls succeed. The sample code provided shows an example of capturing an error, logging that, and returning a known error to the client.

One likely cause of failure is that we release new code that causes problems between the client and the API. We could potentially break our configuration somehow, or alter the contract of our API without thinking about backward compatability. Such issues are likely to manifest as client errors. We can monitor these values are react accordingly. The API Gateway [Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-metrics-and-dimensions.html) details the key metrics we should monitor. 

AWS SAM supports safe deployments of Lambda functions with the `DeploymentPreference` configuration. All functions in this application are configured to use this. This allows automatic traffic shifting between releases, with alarms and pre/post deployment hooks available too. Read the [blog post](https://aws.amazon.com/blogs/compute/implementing-safe-aws-lambda-deployments-with-aws-codedeploy/) which details this further. It is not in scope for this application, but API Gateway also supports canary deployments and this can be used to gradually shift traffic between deployed versions in a similar fashion to the method used Lambda functions. The API Gateway [Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/canary-release.html) has more information on canary releases.  

## Streams To Lambda

This section covers Lambda consuming both Kinesis Data Streams and DynamoDB Streams - these are effectively the same from a failure handling perspective.

The Event Source Mapping manages the invocation of Lambda as a consumer of a Kinesis Data Stream. The number of shards in the stream determines how many functions will process a stream. By default, one batch per shard will be processed at a time. You can increase this by changing the [Parallelization Factor](https://aws.amazon.com/about-aws/whats-new/2019/11/aws-lambda-supports-parallelization-factor-for-kinesis-and-dynamodb-event-sources/). 

Optional configuration properties for the Event Source Mapping include `MaximumRecordAgeInSeconds` and `MaximumRetryAttempts`. If not supplied, these both default to `-1` which means infinite retries. If we have a bad record which causes our function to fail processing, the whole batch for that shard will fail. In this case the failed batch will be retried until the record expires from the stream. As stream consumption is ordered, this means our system could be backed up by a failing record for a long period of time. We can enable `BisectBatchOnFunctionError`, and when a batch fails, Lambda will split the batch and try to process it in two invocations. This can happen multiple times to help isolate failing records into a smaller or individual record batch. It is recommend that you set the above values explicitly to ensure Lambda acts as you expect, and ensure your system can gracefully handle bad records without grinding to a halt. Additionally it is recommended that you monitor the `IteratorAgeMilliseconds` which will help you understand if Lambda is falling further and further behind real-time processing of the stream. This [Knowledge Center](https://aws.amazon.com/premiumsupport/knowledge-center/kinesis-data-streams-iteratorage-metric/) article details how to monitor this metric.

In these patterns we can configure a DLQ as part of the Event Source Mapping. We do so by specifying the `DestinationConfig`. In the sample app, we configure this to send failed records to SQS. Records which are discarded by the Event Source Mapping because they exceed the maximum retry attempts or maximum record age will be sent to this destination. Lambda will then continue to process subsequent records in the stream. Note that the actual records themselves are not sent to the DLQ. Instead you will get pointer information about the shard and sequence numbers of the failed records. You will also get information such as the function error that was raised, and the condition according to which the record was discarded. The failed records remains in the stream, and you must use the DLQ information to retrieve the records before they expire from the stream if you wish to reprocess them. Refer to [Streams DLQ Example](/docs/streams_dlq_example.md) for an example of how to do this.

A further improvement we can make is to report the failure of a specific record within a batch in our Lambda code. This is an improvement over `BisectBatchOnFunctionError` as it means successful records are be less likely to be retried. This is because `BisectBatchOnFunctionError` alone does not have information about which record fails, so it splits the batch evenly for retries. To provide this additional information this we must specify `FunctionResponseTypes` on the Event Source Mapping with a value of `ReportBatchItemFailures`. We then return a data structure from our Lambda function which contains the sequence number of the failed record. Lambda can then bisect the batch at this point as opposed to doing it by simply cutting the batch in half.

To try and illustrate the difference, here is what you might see in a scenario where you had a batch of 10 records, and the 8th was a bad record.

| -  | BisectBatchOnFunctionError  | ReportBatchItemFailures  | 
|---|---|---|
| Records  | 1-10  | 1-10  |  
| Records  | 1-5  | 8-10  | 
| Records  | 6-10  | 8  |  
| Records  | 6-7  | 9-10  |  
| Records  | 8-10  | N/A  |  
| Records  | 8  | N/A  |  
| Records  | 9-10  | N/A  |  

This is illustrative only - you will see varying results based on your retry and max age configuration. By not reporting batch item failures, we can see we have more invocations to get through a problematic batch. Additionally, the records close to the bad record were retried multiple times more than was necessary. It is worth noting however that even when reporting batch failures, we still get multiple invocations for some good records. It is important to account for this in your business logic, for example in the supplied code, records are processed one at a time and we return as soon as a bad record is encountered, meaning our duplicate invocations for good records should not mean they are processed multiple times. If however your function processes records in parallel, this approach would not work, and you may wish to add your own code to handling bad records and moving them somewhere else, e.g. SQS.

As you can see, understanding how your configuration impacts your application is absolutely critical. You may see records retried multiple times and as mentioned above, building your application to be idempotent will reduce the impact if your configuration is not working how you expect. Doing this work up front is far easier than trying to clear your database of thousands of duplicate orders. See this [Knowledge Center](https://aws.amazon.com/premiumsupport/knowledge-center/lambda-function-idempotent/) article for advice on writing idempotent Lambda functions.

## SQS To Lambda

The Event Source Mapping controls how Lambda consumes an SQS queue. It polls the queue for messages and scales out Lambda concurrency based on how many messages in the queue. Each invocation will receive a batch of messages. If there's an error during the processing of a batch, Lambda doesn't delete those messages from the queue. The messages in the batch will return to the queue once the visibility timeout has passed. Lambda would then receive those messages again, but the formation of a batch may be completely different. By default, a failed message will cycle through this loop until the it expires from the queue. Cyclical failures like this may cause your queue to grow as Lambda has repeated failures. Depending on your batch size and the size of your queue, you could end up completely stuck due to a single bad record. The metrics `ApproximateAgeOfOldestMessage` and `ApproximateNumberOfMessagesVisible` are worth monitoring to ensure there are no outstanding issues with processing your queue.

We can mitigate this by adding a DLQ to our design. Unlike streams where we configure this as part of the Event Source Mapping, here we configure the DLQ as part of the source SQS queue. We do this by setting the `RedrivePolicy` of the queue, and we can configure the `maxReceiveCount` property to manage the number of retries Lambda will make. Once Lambda fails to process the message that number of times, SQS will offload the message to the DLQ.

As with streams, Lambda invocations receives batches of messages from SQS. We can specify a `FunctionResponseTypes` of `ReportBatchItemFailures` on our Event Source Mapping here too. Then, in our code, we report on batch failures by returning the appropriate data structure. There is a difference however with SQS, in that we can return the `messageId` of all bad messages in our function response. Lambda will then delete all other messages in the batch from the queue, and so only the failed messages will be subject to retries and potentially be discarded to the DLQ.

## Eventbridge

Eventbridge is used as a means to distribute events to interested subscribers. When we think about failure modes here, we are talking about whether or not Eventbridge can deliver a message to a target or not. We configure a DLQ for a specific target, as opposed to having a DLQ for the whole event bus. When Eventbridge tries to deliver a message to a target, a failure is assessed on whether the error is retryable or not. For example, if Eventbridge lacks permissions to send the event to the target, or the target no longer exists, these events are sent immediately to the DLQ without retry. Other errors may be returned from downstream services, such as a throttle. If the error is considered retryable, Eventbridge will retry according to the DLQ configuration, where you can specify the `MaximumRetryAttempts` and `MaximumEventAgeInSeconds`. If you did not have a DLQ configured, the event would be retried for up to 24 hours before being discarded. More information can be found in the [EventBridge User Guide](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-dlq.html).

As a final note, it should be clear that Eventbridge DLQ is not for capturing failures within target resources (e.g. a Lambda consumer) - it is only for capturing failed delivery of events to those services. It is key that you also configure appropriate failure handling within downstream services. 

## Async Lambda Invocations

In this architecture our Eventbridge rule target is a Lambda function. The invocation is an asychronous invocation, meaning Eventbridge does not wait for the result. The message has been delivered, therefore the role of Eventbridge is complete. If we want to capture events that fail to process here, we can make use of [Lambda Destinations](https://aws.amazon.com/blogs/compute/introducing-aws-lambda-destinations/). This is a feature where we can specify where to send the result of our function in the case of both success and failure. We do this by configuring the Event Source Mapping using the `EventInvokeConfig` property. In addition to capturing failed events, this also gives us control as seen elsewhere by allowing us to configure the number of retries and maximum message age. By default, if we have no failure destination configured, Lambda will attempt to process an async invocation 3 times before discarding the event. This pattern is applicable for all async invocation patterns, some of which are shown in the image from the article linked above:

![Async Lambda Invocations](/images/async-lambda.png)

Any records in the DLQ here will include contextual information including the failed Lambda stack trace and the original record received.

## Redriving Failed Records

Much of this application involves moving failed records to a DLQ. What isn't covered is the next step - processing those records. What does this look like? It depends on your business logic and requirements. Perhaps you deployed a bug which malformed records and you need to push them back through the system. Perhaps they were test events that can be discarded. The most important part is having some plan for how you handle these occurrences. The first key step in all cases is to create an alarm so you are notified that failed records exist. Once you know the records exist, you can go and inspect them to decide what is next.

One approach is to have a 'Redrive Lambda' that consumes the DLQ. The Event Source Mapping can be disabled most of the time. When new failed records arrive, you can update your Redrive Lambda accordingly. This function could repair malformed records, or discard them as necessary. Alternatively, if the numbers are trivial, you can deal with it manually. 

If the DLQ relates to a source SQS queue, you could make use of the console feature to [redrive records to the source queue](https://aws.amazon.com/blogs/compute/introducing-amazon-simple-queue-service-dead-letter-queue-redrive-to-source-queues/). You can even configure the rate at which this occurs so it doesn't negatively impact your system. This approach makes sense if the failed records related to a transient error and you expect them to flow through without issue this time.