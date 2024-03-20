import * as bedrockagents from 'bedrock-agents-cdk';
import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as nodeLambda from 'aws-cdk-lib/aws-lambda-nodejs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { AGENT_NAME, KNOWLEDGE_BASE_NAME, AWS_REGION_NAME } from './constants';
import path = require('path');

export interface AutomateDischargeInstructionsStackProps extends cdk.StackProps {}

const kbInstruction = `
Use this knowledge base to obtain detailed information on the diagnostic provided by the user.`;
const agentInstruction = `
You're a clinician specialized on writing discharge reports on behalf of the doctor.
You'll have access to patient data and diagnostics data.
The user is going to provide information on patient and diagnostic and a template.
Follow the template strictly to generate the desired report.`;

export class BedrockStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props: AutomateDischargeInstructionsStackProps) {
    super(scope, id, props);

    // Dynamo Db
    const patientTable = new dynamodb.Table(this, 'patients-table', {
      tableName: 'patients',
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: false,
      deletionProtection: false,
      tableClass: dynamodb.TableClass.STANDARD,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // KB S3 Bucket
    const kbBucket = new s3.Bucket(this, 'kbBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Lambda
    const getPatientFunction = new nodeLambda.NodejsFunction(this, `get-patient`, {
      runtime: lambda.Runtime.NODEJS_20_X,
      architecture: lambda.Architecture.ARM_64,
      functionName: 'get-patient',
      description: 'Obtain patient data from database with provided ID',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      handler: 'main',
      entry: path.resolve(__dirname, '../src/get-patient/index.ts'),
      bundling: {
        externalModules: ['@aws-sdk/client-dynamodb', '@aws-sdk/lib-dynamodb'],
      },
      environment: {
        TABLE_NAME: patientTable.tableName,
      },
    });
    patientTable.grantFullAccess(getPatientFunction);

    const agentRole = iam.Role.fromRoleArn(this, 'agentRole', cdk.Fn.importValue('agentRoleArn'));
    const kbRole = iam.Role.fromRoleArn(this, 'kbRole', cdk.Fn.importValue('kbRoleArn'));

    // Bedrock
    const diagnosticsKb = new bedrockagents.BedrockKnowledgeBase(this, KNOWLEDGE_BASE_NAME, {
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
          vectorIndexName: `${KNOWLEDGE_BASE_NAME}-default-index`,
        },
        type: 'OPENSEARCH_SERVERLESS',
      },
      dataSource: {
        name: 'diagnostics-kb-datasource',
        dataSourceConfiguration: {
          s3Configuration: {
            bucketArn: kbBucket.bucketArn,
          },
        },
      },
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${AWS_REGION_NAME}::foundation-model/amazon.titan-embed-text-v1`
        }
      }
    });
    diagnosticsKb.node.addDependency(kbBucket);

    const agent = new bedrockagents.BedrockAgent(this, AGENT_NAME, {
      agentName: AGENT_NAME,
      instruction: agentInstruction,
      foundationModel: 'anthropic.claude-instant-v1',
      agentResourceRoleArn: agentRole.roleArn,
      actionGroups: [
        {
          actionGroupName: 'patient-api',
          actionGroupExecutor: getPatientFunction.functionArn,
          s3BucketName: cdk.Fn.importValue('apiSpecBucketName'),
          s3ObjectKey: 'schema.json',
          description: 'API to obtain patient data.',
        },
      ],
      knowledgeBaseAssociations: [
        {
          knowledgeBaseName: KNOWLEDGE_BASE_NAME,
          instruction: kbInstruction,
        },
      ],
    });
    agent.node.addDependency(diagnosticsKb);
  }
}
