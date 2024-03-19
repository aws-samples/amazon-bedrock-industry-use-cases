#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { OpensearchStack } from '../lib/opensearch-stack';
import { RolesStack } from '../lib/roles-stack';
import { BedrockStack } from '../lib/bedrock-stack';
import { ApiSpecStack } from '../lib/api-spec-stack';

const app = new cdk.App();
new RolesStack(app, 'roles', {});
new OpensearchStack(app, 'opensearch', {});
new ApiSpecStack(app, 'api-spec', {});
new BedrockStack(app, 'bedrock', {});
