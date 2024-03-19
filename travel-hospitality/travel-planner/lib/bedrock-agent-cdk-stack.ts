import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { S3Construct } from './constructs/s3-bucket-construct';
import { BedrockIamConstruct } from './constructs/bedrock-agent-iam-construct';
import { LambdaIamConstruct } from './constructs/lambda-iam-construct';
import { LambdaConstruct } from './constructs/lambda-construct';
import { BedrockAgentConstruct } from './constructs/bedrock-agent-construct';

import { AGENT_NAME, API_KEY, AGENT_INSTRUCTION, AGENT_MODEL, AGENT_DESCRIPTION } from './constants';

export interface BedrockAgentCdkProps extends cdk.StackProps {
  readonly specFile: string;
  readonly lambdaFile: string;
}

export class BedrockAgentCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: BedrockAgentCdkProps) {
    super(scope, id, props);

    // Generate random number to avoid roles and lambda duplicates
    const randomPrefix = Math.floor(Math.random() * (10000 - 100) + 100);
    const apiKey = this.node.tryGetContext("apiKey") || API_KEY;
    const agentInstruction = this.node.tryGetContext("agentInstruction") || AGENT_INSTRUCTION;
    const agentName = this.node.tryGetContext("agentName") || AGENT_NAME;
    const agentModel = this.node.tryGetContext("agentModel") || AGENT_MODEL;
    const agentDescription = this.node.tryGetContext("apiKey") || AGENT_DESCRIPTION;
    const lambdaName = `bedrock-agent-lambda-${randomPrefix}`;
    const lambdaRoleName = `bedrock-agent-lambda-role-${randomPrefix}`;
    const agentResourceRoleName = `AmazonBedrockExecutionRoleForAgents_${randomPrefix}`; 

    const lambdaRole = new LambdaIamConstruct(this, `LambdaIamConstruct-${randomPrefix}`, { roleName: lambdaRoleName });
    const s3Construct = new S3Construct(this, `agent-assets-${randomPrefix}`, {});
    const bedrockAgentRole = new BedrockIamConstruct(this, `BedrockIamConstruct-${randomPrefix}`, { 
      roleName: agentResourceRoleName,
      lambdaRoleArn: lambdaRole.lambdaRole.roleArn,
      s3BucketArn: s3Construct.bucket.bucketArn,
    });
    bedrockAgentRole.node.addDependency(lambdaRole);
    bedrockAgentRole.node.addDependency(s3Construct);
    const agentLambdaConstruct = new LambdaConstruct(this, `LambdaConstruct-${randomPrefix}`, {
      apiKey: apiKey,
      lambdaName: lambdaName,
      lambdaFile: props.lambdaFile,
      lambdaRoleName: lambdaRoleName,
      iamRole: lambdaRole.lambdaRole
    });
    agentLambdaConstruct.node.addDependency(lambdaRole);

    const bedrockAgentConstruct = new BedrockAgentConstruct(this, `BedrockConstruct-${randomPrefix}`, {
      apiKey: apiKey,
      agentName: agentName,
      agentModel: agentModel,
      agentInstruction: agentInstruction,
      agentDescription: agentDescription,
      agentRoleArn: bedrockAgentRole.roleArn,
      lambdaArn: agentLambdaConstruct.lambdaArn,
      s3BucketName: s3Construct.bucketName
    });
    bedrockAgentConstruct.node.addDependency(bedrockAgentRole);
    bedrockAgentConstruct.node.addDependency(s3Construct);
    bedrockAgentConstruct.node.addDependency(agentLambdaConstruct);
  }
}
