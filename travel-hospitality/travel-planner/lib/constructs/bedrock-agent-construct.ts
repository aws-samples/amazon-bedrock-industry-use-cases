import * as bedrockagents from 'bedrock-agents-cdk';
import * as cdk from 'aws-cdk-lib';
import { Construct } from "constructs";

export interface AutomateDischargeInstructionsStackProps extends cdk.StackProps {}

export interface BedrockProps extends cdk.StackProps {
  readonly apiKey: string;
  readonly agentName: string;
  readonly agentInstruction: string;
  readonly agentDescription: string;
  readonly agentModel: string;
  readonly agentRoleArn: string;
  readonly lambdaArn: string;
  readonly s3BucketName: string;
}

const defaultProps: Partial<BedrockProps> = {};

export class BedrockAgentConstruct extends Construct {
  public agentName: string;

  constructor(scope: Construct, name: string, props: BedrockProps) {
    super(scope, name);

    props = { ...defaultProps, ...props };

    const agent = new bedrockagents.BedrockAgent(this, props.agentName, {
      agentName: props.agentName,
      instruction: props.agentInstruction,
      description: props.agentDescription,
      foundationModel: props.agentModel,
      agentResourceRoleArn: props.agentRoleArn,
      actionGroups: [
        {
          actionGroupName: 'travel-api',
          actionGroupExecutor: props.lambdaArn,
          s3BucketName: props.s3BucketName,
          s3ObjectKey: 'api-schema/schema.json',
          description: 'API to obtain flights and hotels from SerpAPI.',
        },
      ],
    });

    new cdk.CfnOutput(this, "BedrockAgentArn", {
      value: agent.agentArn,
    });

  }
}
