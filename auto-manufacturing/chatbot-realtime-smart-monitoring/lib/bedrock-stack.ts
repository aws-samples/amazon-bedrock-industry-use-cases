import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import { AGENT_NAME, KNOWLEDGE_BASE_NAME, AWS_REGION_NAME } from './constants';

export class BedrockStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const kbInstruction = `Use this knowledge base to obtain information regarding equipment maintenance manuals and instructions.`;
    const agentInstruction = `You're a maintenance technician specialized in troubleshooting equipment readings based on predefined manuals of procedures and troubleshooting step.
The user may ask you questions pertaining readings from equipment telemetry, your job is to figure out steps and procedures from available data sources how and give the instructions in a detailed way to the user.`;

    const kbBucket = new s3.Bucket(this, 'kb-bucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
    });

    new cdk.CfnOutput(this, 'kb-bucket-name', { value: kbBucket.bucketName });

    const agentRole = iam.Role.fromRoleArn(this, 'agentRole', cdk.Fn.importValue('agentRoleArn'));
    const kbRole = iam.Role.fromRoleArn(this, 'kbRole', cdk.Fn.importValue('kbRoleArn'));

    const diagnosticsKb = new bedrock.CfnKnowledgeBase(this, 'mfg-kb', {
      name: KNOWLEDGE_BASE_NAME,
      roleArn: kbRole.roleArn,
      storageConfiguration: {
        opensearchServerlessConfiguration: {
          collectionArn: cdk.Fn.importValue('opensearchArn'),
          fieldMapping: {
            metadataField: 'metadata',
            textField: 'text',
            vectorField: 'vector',
          },
          vectorIndexName: `mfg-vector-index`,
        },
        type: 'OPENSEARCH_SERVERLESS',
      },
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${AWS_REGION_NAME}::foundation-model/amazon.titan-embed-text-v1`,
        },
      },
    });
    new bedrock.CfnDataSource(this, 'mfg-kb-source', {
      name: 'diagnostics-kb-datasource',
      knowledgeBaseId: diagnosticsKb.attrKnowledgeBaseId,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: kbBucket.bucketArn,
        },
      },
    });

    const agent = new bedrock.CfnAgent(this, AGENT_NAME, {
      agentName: AGENT_NAME,
      instruction: agentInstruction,
      foundationModel: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
      agentResourceRoleArn: agentRole.roleArn,
      autoPrepare: false,
      knowledgeBases: [
        {
          description: kbInstruction,
          knowledgeBaseId: diagnosticsKb.attrKnowledgeBaseId,
          knowledgeBaseState: 'ENABLED',
        },
      ],
    });

    const agentAlias = new bedrock.CfnAgentAlias(this, 'agent-alias', {
      agentAliasName: 'DraftAlias',
      agentId: agent.attrAgentId,
    });
    agentAlias.addDependency(agent);

    // Export agent ID and alias ID
    new cdk.CfnOutput(this, 'AgentId', {
      value: agent.attrAgentId,
      exportName: 'AgentId',
    });

    new cdk.CfnOutput(this, 'AgentAliasId', {
      value: agentAlias.attrAgentAliasId,
      exportName: 'AgentAliasId',
    });
  }
}
