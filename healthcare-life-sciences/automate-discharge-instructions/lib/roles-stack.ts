import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { AGENT_NAME, KNOWLEDGE_BASE_NAME } from './constants';
import { ServiceLinkedRole } from 'upsert-slr';

export class RolesStack extends cdk.Stack {
    public constructor(scope: cdk.App, id: string, props: any) {
        super(scope, id, props);

        const agentRole = new iam.Role(this, 'bedrockAgentRole', {
            roleName: `AmazonBedrockExecutionRoleForAgents_${AGENT_NAME}`,
            assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
            managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
        });

        const kbRole = new iam.Role(this, 'bedrockKbRole', {
            roleName: `AmazonBedrockExecutionRoleForKnowledgeBase_${KNOWLEDGE_BASE_NAME}`,
            assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
            managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
        });

        // const serviceRole = new iam.CfnServiceLinkedRole(this, 'opensearchServiceRole', {
        //     awsServiceName: 'observability.aoss.amazonaws.com',
        // });
        // serviceRole.cfnOptions.deletionPolicy = cdk.CfnDeletionPolicy.RETAIN;

        new ServiceLinkedRole(this, 'opensearchServiceRole', {
            awsServiceName: 'observability.aoss.amazonaws.com',
            description: 'Service linked role for OpenSearch Serverless',
        });

        new cdk.CfnOutput(this, "agentRoleArn", {
            value: agentRole.roleArn,
            exportName: "agentRoleArn",
        });
        new cdk.CfnOutput(this, "kbRoleArn", {
            value: kbRole.roleArn,
            exportName: "kbRoleArn",
        });
    }
}
