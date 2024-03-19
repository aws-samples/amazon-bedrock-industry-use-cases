export interface AmazonBedrockActionGroupOutput {
  messageVersion: '1.0';
  response: {
    actionGroup: string;
    apiPath: string;
    httpMethod: string;
    httpStatusCode: number;
    responseBody: {
      [contentType: string]: {
        body: string;
      };
    };
    sessionAttributes?: {
      [key: string]: string;
    };
    promptSessionAttributes?: {
      [key: string]: string;
    };
  };
}
