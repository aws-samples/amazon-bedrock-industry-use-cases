#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { RolesStack } from '../lib/roles-stack';
import { BedrockStack } from '../lib/bedrock-stack';
import { OpensearchStack } from '../lib/opensearch-stack';
import { UIStack } from '../lib/ui-stack';
import { ApiStack } from '../lib/api-stack';

const app = new cdk.App();
new RolesStack(app, 'roles-stack', {});
new OpensearchStack(app, 'opensearch-stack', {});
new BedrockStack(app, 'bedrock-stack', {});
new ApiStack(app, 'api-stack', {});
new UIStack(app, 'ui-stack', {});
