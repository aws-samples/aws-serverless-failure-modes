# Streams DLQ Example

Records in a DLQ remain in the original stream and follow the normal lifecyle for expiry, depending on how the stream is configured. The information in the DLQ allows you to retrive the record from the stream, and involves multiple API calls.

This is an example record body for a DLQ message:

```
{"requestContext":{"requestId":"4a495e66-0520-4154-9030-2e6bb46cc99e","functionArn":"arn:aws:lambda:eu-west-1:012345678901:function:aws-sls-failure-modes-KinesisLambda-9oSoHNgR0o3d:live","condition":"RetryAttemptsExhausted","approximateInvokeCount":3},"responseContext":{"statusCode":200,"executedVersion":"1","functionError":null},"version":"1.0","timestamp":"2022-01-10T15:40:03.863Z","KinesisBatchInfo":{"shardId":"shardId-000000000000","startSequenceNumber":"49625681492847716055798994229222865552900196919517642754","endSequenceNumber":"49625681492847716055798994229222865552900196919517642754","approximateArrivalOfFirstRecord":"2022-01-10T15:40:01.427Z","approximateArrivalOfLastRecord":"2022-01-10T15:40:01.427Z","batchSize":1,"streamArn":"arn:aws:kinesis:eu-west-1:012345678901:stream/aws-sls-failure-modes-KinesisStream-VNyLC42KYxKD"}}
```

Note this does not contain any content of the original record. Querying a stream requires a Shard Iterator, which effectively points to a location in a stream. To obtain this we can make an API call using the DLQ record, e.g.

```
aws kinesis get-shard-iterator \
    --stream-name aws-sls-failure-modes-KinesisStream-VNyLC42KYxKD \
    --shard-id shardId-000000000000 \
    --shard-iterator-type AT_SEQUENCE_NUMBER \
    --starting-sequence-number 49625681492847716055798994229222865552900196919517642754
```

This returns the Shard Iterator:

```
{
    "ShardIterator": "AAAAAAAAAAG+kjzHqmnZxKamqGpvEORtTSG4r7xXj+FIrpjhK9X982lHNuZArLqvucTDg5G8HPjhbtRqhltm+37iGCoIfHQaDp3+pO38dsFAS1sgwHUPrjWF2BejA0fSOypr7j1g3BALerk5gxp5taD68EEYgabCmWRrKl9jdgs4QnkwScNYPTHhDfqXm1UuU80hIH9DLIC499K0XbjNkYIoN9GajV18MAFa/bRS2ErzyV+RHGIRkWxJeaBlKPF7K7vqJMZ6C8YGqToa9OoLT3QDk45JQ+q5"
}
```

We can then use this to obtain records as desired.

```
aws kinesis get-records \
    --shard-iterator AAAAAAAAAAG+kjzHqmnZxKamqGpvEORtTSG4r7xXj+FIrpjhK9X982lHNuZArLqvucTDg5G8HPjhbtRqhltm+37iGCoIfHQaDp3+pO38dsFAS1sgwHUPrjWF2BejA0fSOypr7j1g3BALerk5gxp5taD68EEYgabCmWRrKl9jdgs4QnkwScNYPTHhDfqXm1UuU80hIH9DLIC499K0XbjNkYIoN9GajV18MAFa/bRS2ErzyV+RHGIRkWxJeaBlKPF7K7vqJMZ6C8YGqToa9OoLT3QDk45JQ+q5
```

Which returns:

```
{
    "Records": [
        {
            "SequenceNumber": "49625681492847716055798994229222865552900196919517642754",
            "ApproximateArrivalTimestamp": "2022-01-10T15:40:01.427000+00:00",
            "Data": "eyJzb21ldGhpbmciOiAidmFsdWUiLCAiaWQiOiAiYmEzNDA5MzItYjUyOC00Mzc3LTlkNGYtYzJiOWViYWJiOWYxX2Vycm9yIn0=",
            "PartitionKey": "ba340932-b528-4377-9d4f-c2b9ebabb9f1_error"
        }
    ],
    "NextShardIterator": "AAAAAAAAAAGi295eEeatO5Qr1+ZoqXREZYzp0WgNHzx3Yhi9ahebloV77tY8QiINX3NUki7mIsgOY4+cU+BsjskCnmPjW5UBx8UCqcLiS3OtF3fBq9wwaiWKb+nGrsOVq35iEjAOzzC4HZFikWHIlr9Ddf5IFEI6N52O9q/tC1H1y4LlsH52WjhEAt/DFL5OtjSgDtOiFWZmhd7TdGpMQv6sAY5Gka2ywLvRCBcJqzqHiiBqYhjs7hBiKnJR1ePDxEH3oUw2OwWmOjWfSW5OxgruRrPgPwwh",
    "MillisBehindLatest": 0
}
```

Note the `Data` field is Base64 encoded, so you must decode that to read the data, e.g.

```
echo eyJzb21ldGhpbmciOiAidmFsdWUiLCAiaWQiOiAiYmEzNDA5MzItYjUyOC00Mzc3LTlkNGYtYzJiOWViYWJiOWYxX2Vycm9yIn0= | base64 --decode
```

This gives the original content of the record in the DLQ, which we can use to reprocess as required:

```
{"something": "value", "id": "ba340932-b528-4377-9d4f-c2b9ebabb9f1_error"}
```