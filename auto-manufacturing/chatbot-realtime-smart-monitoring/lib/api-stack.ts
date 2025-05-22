import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as nodeLambda from 'aws-cdk-lib/aws-lambda-nodejs';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigatewayv2_integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import path = require('path');

export class ApiStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // HTTP API Gateway
    const httpApi = new apigatewayv2.HttpApi(this, 'troubleshoot-api', {
      corsPreflight: {
        allowOrigins: ['*'],
        allowMethods: [apigatewayv2.CorsHttpMethod.POST],
        allowHeaders: ['*'],
      },
    });

    // Lambda
    const troubleshootSensorFunction = new nodeLambda.NodejsFunction(this, `troubleshoot-sensor`, {
      runtime: lambda.Runtime.NODEJS_22_X,
      architecture: lambda.Architecture.ARM_64,
      functionName: 'troubleshoot-sensor',
      description: 'Troubleshoot sensor data using LLM and knowledge base',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      handler: 'handler',
      entry: path.resolve(__dirname, '../src/troubleshoot-sensor.ts'),
      bundling: {
        externalModules: ['@aws-sdk/client-bedrock-agent-runtime'],
      },
      initialPolicy: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['bedrock:InvokeAgent'],
          resources: [
            `arn:aws:bedrock:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:agent/${cdk.Fn.importValue('AgentId')}`,
            `arn:aws:bedrock:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:agent-alias/${cdk.Fn.importValue('AgentId')}/${cdk.Fn.importValue('AgentAliasId')}`,
          ],
        }),
      ],
      environment: {
        AGENT_ID: cdk.Fn.importValue('AgentId'),
        AGENT_ALIAS_ID: cdk.Fn.importValue('AgentAliasId'),
      },
    });

    // Add route integration
    const troubleshootIntegration = new apigatewayv2_integrations.HttpLambdaIntegration('TroubleshootIntegration', troubleshootSensorFunction);
    httpApi.addRoutes({
      path: '/troubleshooting-info',
      methods: [apigatewayv2.HttpMethod.POST],
      integration: troubleshootIntegration,
    });

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: httpApi.apiEndpoint,
      exportName: 'TroubleshootApiEndpoint',
    });
  }
}
