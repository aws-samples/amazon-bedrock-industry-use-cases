import { BedrockAgentRuntimeClient, InvokeAgentCommand } from '@aws-sdk/client-bedrock-agent-runtime';
import { APIGatewayEventRequestContextV2, APIGatewayProxyResultV2 } from 'aws-lambda';
import { randomUUID } from 'crypto';

// Initialize client outside the handler for connection reuse across invocations
const bedrockClient = new BedrockAgentRuntimeClient({});

/**
 * Lambda handler to process sensor data using AWS Bedrock Agent
 * @param {Object} event - API Gateway event
 * @returns {Object} API Gateway response
 */
export const handler = async (event: APIGatewayEventRequestContextV2): Promise<APIGatewayProxyResultV2> => {
  try {
    // Parse request body
    const body = parseEventBody(event);

    // Extract parameters
    const { sensor, reading, sessionId, userPrompt } = body;

    // Validate parameters - check for valid combinations
    if (sensor && reading && !(sessionId && userPrompt)) {
      // Use case 1: sensor data
      return await processSensorData(sensor, reading);
    } else if (sessionId && userPrompt && !(sensor && reading)) {
      // Use case 2: direct user prompt
      return await processUserPrompt(sessionId, userPrompt);
    } else {
      // Invalid parameter combination
      return createResponse(400, {
        message: 'Invalid parameters. Provide either (sensor and reading) OR (sessionId and userPrompt)',
      });
    }
  } catch (error: any) {
    console.error('Error processing request:', error);
    // Handle any errors
    return createResponse(500, {
      message: 'Internal server error',
      error: error.message,
    });
  }
};

/**
 * Parse API Gateway event body
 * @param {Object} event - API Gateway event
 * @returns {Object} Parsed body
 */
function parseEventBody(event: any) {
  if (!event.body) return {};

  const bodyString = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf-8') : event.body;

  try {
    return JSON.parse(bodyString);
  } catch (error) {
    throw new Error('Invalid JSON in request body');
  }
}

/**
 * Process sensor data
 * @param {string} sensor - Sensor ID
 * @param {string} reading - Sensor reading
 * @returns {Object} API Gateway response
 */
async function processSensorData(sensor: string, reading: string) {
  const sessionId = randomUUID();
  const prompt = createSensorPrompt(sensor, reading);

  // Call Bedrock agent and get response
  const completion = await invokeAgent(sessionId, prompt);

  // Return successful response
  return createResponse(200, {
    response: completion,
    sessionId: sessionId,
  });
}

/**
 * Create prompt for sensor data
 * @param {string} sensor - Sensor ID
 * @param {string} reading - Sensor reading
 * @returns {string} Formatted prompt
 */
function createSensorPrompt(sensor: string, reading: string) {
  return `
  Based on existing documentation for troubleshooting, provide the resolution and actions steps to troubleshoot and resolve:
  Sensor: ${sensor}
  Reading: ${reading}
  
  Be very specific with the actions for the above type of metric and the reading that the operator received.
  If no troubleshooting steps are available for this sensor, then tell the user that and do not attempt to provide instructions.`;
}

/**
 * Process user prompt directly
 * @param {string} sessionId - Conversation session ID
 * @param {string} userPrompt - User's prompt
 * @returns {APIGatewayProxyResultV2} API Gateway response
 */
async function processUserPrompt(sessionId: string, userPrompt: string): Promise<APIGatewayProxyResultV2> {
  // Call Bedrock agent and get response
  const completion = await invokeAgent(sessionId, userPrompt);

  // Return successful response
  return createResponse(200, {
    response: completion,
    sessionId: sessionId,
  });
}

/**
 * Invoke Bedrock Agent with prompt
 * @param {string} sessionId - Session ID
 * @param {string} inputText - Prompt text
 * @returns {Promise<string>} Agent's response
 */
async function invokeAgent(sessionId: string, inputText: string): Promise<string> {
  try {
    // Call Bedrock agent
    const response = await bedrockClient.send(
      new InvokeAgentCommand({
        agentId: process.env.AGENT_ID!,
        agentAliasId: process.env.AGENT_ALIAS_ID!,
        sessionId: sessionId,
        inputText: inputText,
      })
    );

    // Process the agent's response
    return await processAgentResponse(response);
  } catch (error: any) {
    console.error('Error invoking Bedrock agent:', error);
    throw new Error(`Failed to get response from Bedrock agent: ${error.message}`);
  }
}

/**
 * Process the streaming response from Bedrock Agent
 * @param {Object} response - The response from Bedrock Agent
 * @returns {Promise<string>} The completed response text
 */
async function processAgentResponse(response: any) {
  if (!response.completion) {
    return 'No response received from agent.';
  }

  let completion = '';

  try {
    for await (const event of response.completion) {
      if (event.chunk && event.chunk.bytes) {
        const decodedChunk = new TextDecoder('utf-8').decode(event.chunk.bytes);
        completion += decodedChunk;
      }
    }
    return completion;
  } catch (error: any) {
    console.error('Error processing agent response stream:', error);
    throw new Error(`Error processing agent response: ${error.message}`);
  }
}

/**
 * Create a formatted API Gateway response
 * @param {number} statusCode - HTTP status code
 * @param {Object} body - Response body
 * @returns {Object} Formatted response
 */
function createResponse(statusCode: number, body: any): APIGatewayProxyResultV2 {
  return {
    statusCode,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}
