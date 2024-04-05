# Travel Planner
================

## Authors:
- [Armando Diaz](https://www.linkedin.com/in/armando-diaz-47a498113/) @armdiazg 
- [Marco Punio](https://www.linkedin.com/in/marcpunio/) @puniomp

This guide details how to install, configure, and use the agent CDK deployment. The instructions assume that the deployment will be deployed from a terminal running from Linux or MacOS.

Resources provisioned by deployment:

* S3 bucket
* Bedrock Agent
* Bedrock Agent IAM role
* Bedrock Agent Action Group
* Lambda function
* Lambda service-policy permission 
* Lambda IAM role

The tutorial deploys Bedrock agent backed by Anthropic Clause V2 model and creates an Action Group within this agent with the schema located in ``lib/assets/api-schema`` and Python function located in ``lib/assets/lambda``. To do that, the demo also creates an S3 bucket and uploads schema to it. IAM roles are provisioned by CDK. Make sure to modify the policies appropriate for your needs.

# Prerequisites
===============

* [SerpApi API Key](https://serpapi.com/)
   1) Go to https://serpapi.com/dashboard
   2) Sign in to your Serp API account or create one if you don't have it.
   3) In your dashboard, generate an API key. This key will be essential for accessing the Serp API services and stack deployment.
* [node](https://nodejs.org/en) >= 16.0.0
* [npm](https://www.npmjs.com/) >= 8.0.0
* [AWS CLI](https://aws.amazon.com/cli/) >= 2.0.0
* [AWS CDK](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-construct-library.html) >= 2.130.0
* [Docker](https://www.docker.com/):
   - Install [Docker](https://docs.docker.com/desktop/) or
   - Create an [AWS Cloud9](https://docs.aws.amazon.com/cloud9/latest/user-guide/create-environment-main.html) environment

*Note: In some cases, you might need to authenticate Docker to Amazon ECR registry with get-login-password. Run the aws ecr [get-login-password](https://docs.aws.amazon.com/AmazonECR/latest/userguide/getting-started-cli.html) command. `aws ecr get-login-password --region region | docker login --username AWS --password-stdin aws_account_id.dkr.ecr.region.amazonaws.com`*

# How to run

From within the root project folder (``travel-planner``), run the following commands:

```sh
npm install
```
Note - if you have `npm ERR!` erros related to overlapping dependencies, run `npm install --force`.
```sh
cdk bootstrap
```

Substitute "my-api-key" with your SerpApi Api Key:
```sh
cdk deploy -c apiKey="my-api-key"
```

Optional - if you want to change the [default settings](lib/constants.ts) you can deploy the stack like this (substituting "my-agent-name", "my-api-key", "my-agent-instruction", "my-agent-model", or "my-agent-description" with your desired values):

```sh
cdk deploy -c agentName="my-agent-name" -c apiKey="my-api-key" -c agentInstruction="my-agent-instruction" -c agentModel="my-agent-model" -c agentDescription="my-agent-description"
```

# Sample prompts:

+ *What is the cheapest flight from Atlanta to Miami in October, 2024?*
+ *Can you find me a hotel under $150/night in San Francisco from December 4th to December 15th, 2024?*

# Automatic OpenAPI generator with Powertools for AWS Lambda (Python):

The [OpenAPI schema](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-api-schema.html) defines a group of APIs that the agent can invoke. You can create your own OpenAPI schema following our [example](lib/assets//api-schema/create_openapi_schema.py), which autogenerates an OpenAPI schema in JSON using [Powertools for AWS Lambda](https://github.com/aws-powertools/powertools-lambda-python).

# How to delete

From within the root project folder (``travel-planner``), run the following command:

```sh
cdk destroy --force
```

**Note - if you created any aliases/versions within your agent you would have to manually delete it in the console.**
