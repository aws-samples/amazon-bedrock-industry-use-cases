import * as cdk from 'aws-cdk-lib';
import * as custom from 'aws-cdk-lib/custom-resources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import { COLLECTION_NAME, METADATA_FIELD_NAME, TEXT_FIELD_NAME, VECTOR_FIELD_NAME, VECTOR_INDEX_NAME } from './constants';


export class OpensearchStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props: any) {
    super(scope, id, props);

    const kbRole = iam.Role.fromRoleArn(this, 'kbRole', cdk.Fn.importValue('kbRoleArn'));
    const customResourceRole = new iam.Role(this, 'index-custom-resource-role', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
    });

    const accessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'opensearchAccessPolicy', {
      policy: JSON.stringify([
        {
          Description: "Data access policy to grant access to Amazon Bedrock Knowledge Base",
          Rules: [
            { Resource: [`collection/${COLLECTION_NAME}`], Permission: ["aoss:DescribeCollectionItems", "aoss:CreateCollectionItems", "aoss:UpdateCollectionItems"], ResourceType: "collection" },
            { Resource: [`index/${COLLECTION_NAME}/*`], Permission: ["aoss:UpdateIndex", "aoss:DescribeIndex", "aoss:ReadDocument", "aoss:WriteDocument", "aoss:CreateIndex"], ResourceType: "index" },
          ],
          Principal: [kbRole.roleArn, customResourceRole.roleArn]
        }
      ]),
      type: 'data',
      description: 'Data access policy to grant access to Amazon Bedrock Knowledge Base.',
      name: 'diagnostics-kb-access-policy',
    });

    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'opensearchEncryptionPolicy', {
      policy: JSON.stringify({ Rules: [{ Resource: [`collection/${COLLECTION_NAME}`], ResourceType: "collection" }], AWSOwnedKey: true }),
      type: 'encryption',
      description: 'Encryption policy for Amazon Bedrock Knowledge Base vector database.',
      name: 'diagnostics-kb-encryption-policy',
    });

    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'opensearchNetworkPolicy', {
      policy: JSON.stringify([{
        Rules: [
          { Resource: [`collection/${COLLECTION_NAME}`], ResourceType: "dashboard" },
          { Resource: [`collection/${COLLECTION_NAME}`], ResourceType: "collection" }
        ],
        AllowFromPublic: true
      }]),
      type: 'network',
      description: 'Custom network policy created by Amazon Bedrock Knowledge Base service to allow a created IAM role to have permissions on Amazon Open Search collections and indexes.',
      name: 'diagnostics-kb-network-policy',
    });

    const opensearchCollection = new opensearchserverless.CfnCollection(this, 'opensearchCollection', {
      name: COLLECTION_NAME,
      description: 'Diagnostics Amazon Bedrock Knowledge Base vector database',
      type: 'VECTORSEARCH',
    });

    opensearchCollection.node.addDependency(encryptionPolicy);
    opensearchCollection.node.addDependency(networkPolicy);
    opensearchCollection.node.addDependency(accessPolicy);

    // Vector Index
    // API Access
    customResourceRole.addToPolicy(
      new iam.PolicyStatement({
        resources: [opensearchCollection.attrArn],
        actions: ['aoss:APIAccessAll'],
      }),
    );

    // Lambda Function
    const indexCusstomResourceFunction = new lambda.DockerImageFunction(this, "index-custom-resource-function", {
      code: lambda.DockerImageCode.fromImageAsset('index-custom-resource'),
      timeout: cdk.Duration.seconds(600),
      role: customResourceRole,
      environment: {
        COLLECTION_ENDPOINT: opensearchCollection.attrCollectionEndpoint,
        VECTOR_FIELD_NAME: VECTOR_FIELD_NAME,
        VECTOR_INDEX_NAME: VECTOR_INDEX_NAME,
        TEXT_FIELD: TEXT_FIELD_NAME,
        METADATA_FIELD: METADATA_FIELD_NAME,
        },
    }
    );
    indexCusstomResourceFunction.node.addDependency(opensearchCollection);

    // Custom Resource Provider
    const provider = new custom.Provider(this, 'index-custom-resource-provider', {
      onEventHandler: indexCusstomResourceFunction,
      logRetention: logs.RetentionDays.ONE_DAY,
    });

    // Custom Resource
    new cdk.CustomResource(this, 'index-custom-resource', {
      serviceToken: provider.serviceToken,
    });

    new cdk.CfnOutput(this, "opensearchArn", {
      value: opensearchCollection.attrArn,
      exportName: "opensearchArn",
    });
  }
}
