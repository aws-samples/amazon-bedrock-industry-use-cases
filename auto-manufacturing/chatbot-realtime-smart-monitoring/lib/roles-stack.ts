import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { AGENT_NAME, KNOWLEDGE_BASE_NAME } from './constants';
import { ServiceLinkedRole } from 'upsert-slr';

export class RolesStack extends cdk.Stack {
  public constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const agentRole = new iam.Role(this, 'bedrock-agent-role', {
      roleName: `AmazonBedrockExecutionRoleForAgents_${AGENT_NAME}`,
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
    });

    const kbRole = new iam.Role(this, 'bedrock-kb-role', {
      roleName: `AmazonBedrockExecutionRoleForKnowledgeBase_${KNOWLEDGE_BASE_NAME}`,
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
    });

    // Create service-linked role for OpenSearch Serverless
    new ServiceLinkedRole(this, 'opensearch-service-role', {
      awsServiceName: 'observability.aoss.amazonaws.com',
      description: 'Service linked role for OpenSearch Serverless',
    });

    new cdk.CfnOutput(this, 'agent-role-arn', { value: agentRole.roleArn, exportName: 'agentRoleArn' });
    new cdk.CfnOutput(this, 'kb-role-arn', { value: kbRole.roleArn, exportName: 'kbRoleArn' });
  }
}
