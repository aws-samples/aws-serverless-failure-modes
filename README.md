# Serverless failure modes

## Introduction

This is a sample application that deploys some common serverless patterns and implements failure handling for each component. This is accompanied by the [Failure Modes](/docs/failure_modes.md) document, which describes the thinking behind the design for each part.

## High-level Architecture

This application deploys the following architecture. Some elements such as CloudWatch Alarms are omitted for clarity. Each box in the diagram corresponds to a section in the failure modes document.

![Async Lambda Invocations](/images/high-level-arch.png)

## Deployment

Follow steps described [here](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) to install AWS SAM

Next we deploy the application:

```
sam deploy --guided
```

Enter a stack name e.g. `aws-sls-failure-modes`  
Enter a region e.g. `eu-west-1`  
Enter an environment name e.g. `dev`  
Enter an email to receive Alarm Notifications e.g. `you@email.com`  
For Confirm changes before deploy choose `N`  
For Allow SAM CLI IAM role creation choose `Y`  
For Disable rollback choose `N`  
For APILambda may not have authorization defined, Is this okay? Choose `Y`  
For Save arguments to configuration file choose `Y`  
Accept the default name `samconfig.toml`  
For SAM configuration environment enter `default`  


For subsequent deploys you can just run `sam deploy`

## Test Events

After deploying, you can send in some test events to the application. This include some successful and error messages. After a short period you will be able to inspect the SQS console to view messages in the respective DLQs.

Setup a virtual environment
```
python3 -m venv .venv 
source .venv/bin/activate
pip install -r requirements.txt 
python3 test.py
```

Note that the script `test.py` depends upon `samconfig.toml` created during the deployment steps.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
