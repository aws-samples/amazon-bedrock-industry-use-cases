import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand } from '@aws-sdk/lib-dynamodb';
import { Context } from 'aws-lambda';
import { AmazonBedrockActionGroupInput } from '../types/bedrock-action-group-input';
import { AmazonBedrockActionGroupOutput } from '../types/bedrock-action-group-output';

export const main = async (event: AmazonBedrockActionGroupInput, context: Context): Promise<AmazonBedrockActionGroupOutput> => {
  return await new GetPatient().handler(event, context);
};

export class GetPatient {
  private docClient: DynamoDBDocumentClient;

  constructor() {
    const client = new DynamoDBClient({});
    this.docClient = DynamoDBDocumentClient.from(client);
  }

  public async handler(event: AmazonBedrockActionGroupInput, _context: Context) {
    const command = new GetCommand({
      TableName: process.env['TABLE_NAME'],
      Key: {
        id: event.parameters?.[0]?.value ?? '<no-id>',
      },
    });
    const response = await this.docClient.send(command);

    const actionResponse = {
      actionGroup: event.actionGroup,
      apiPath: event.apiPath,
      httpMethod: event.httpMethod,
      httpStatusCode: 200,
      responseBody: {
        'application/json': {
          body: JSON.stringify(response?.Item ?? {}),
        },
      },
      sessionAttributes: event.sessionAttributes,
      promptSessionAttributes: event.promptSessionAttributes,
    };

    const apiResponse: AmazonBedrockActionGroupOutput = {
      messageVersion: '1.0',
      response: actionResponse,
    };

    return apiResponse;
  }
}
