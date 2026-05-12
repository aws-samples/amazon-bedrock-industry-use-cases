import boto3
from botocore.exceptions import ClientError
from .helper_functions import wait_for_completion
import concurrent.futures
import logging
import random
import string
from IPython.display import display
import pandas as pd
from ipywidgets import Tab, Output, HTML

logging.basicConfig(format='[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def get_document_configuration(document_id, plan_name, plan_document_s3_uri): 
    return {
                "content": {
                    "custom": {
                        "customDocumentIdentifier": {
                            "id": document_id
                        },
                        "s3Location": {
                            "uri": plan_document_s3_uri
                        },
                        "sourceType": "S3_LOCATION"
                    },
                    "dataSourceType": "CUSTOM"
                },
                "metadata": {
                    "inlineAttributes": [
                        {
                            "key": "plan_name",
                            "value": {
                                "stringValue": plan_name,
                                "type": "STRING"
                            }
                        }
                    ],
                    "type": "IN_LINE_ATTRIBUTE"
                }
            }


def create_agent_alias(bedrock_agent, agentAliasName, agentId, description):

    try:
        agent_alias_list = bedrock_agent.list_agent_aliases(agentId=agentId)
        existing_alias = next((agent for agent in agent_alias_list['agentAliasSummaries']
                                if agent['agentAliasName'] == agentAliasName), None)
        agentAliasId = None
        if(existing_alias):
            agentAliasId = existing_alias['agentAliasId']
            bedrock_agent.update_agent_alias(
                agentAliasId=agentAliasId,
                agentAliasName=agentAliasName,
                agentId=agentId,
                description=description,
            )
        else:
            create_agent_alias_response = bedrock_agent.create_agent_alias(
                agentAliasName=agentAliasName,
                agentId=agentId,
                description=description
            )
            agentAliasId = create_agent_alias_response['agentAlias']['agentAliasId']
        status_response = wait_for_completion(
            bedrock_agent,
            bedrock_agent.get_agent_alias,
            {
                'agentId': agentId,
                'agentAliasId':agentAliasId
            },
            'agentAlias.agentAliasStatus',
            ['PREPARED'],
            ['FAILED'],
            max_iterations=10,
            delay=5,
        )
        status = status_response['agentAlias']['agentAliasStatus']
        print(f"{'Updated' if existing_alias else 'Created'} agent alias with name {agentAliasName} and current status {status}")
        return agentAliasId, status
    except ClientError as e:
        print(f"Error creating or retrieving agent: {e}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise


def associate_agent_knowledge_base(bedrock_agent, agentId, agentVersion, description, knowledgeBaseId, knowledgeBaseState):

    agents_kb_list = bedrock_agent.list_agent_knowledge_bases(
                        agentId=agentId,
                        agentVersion=agentVersion)
    existing_agent_kb = next((agent_kb for agent_kb in agents_kb_list['agentKnowledgeBaseSummaries']
                        if agent_kb['knowledgeBaseId'] == knowledgeBaseId), None)
    if existing_agent_kb:
        print(f'Knowledge Base {knowledgeBaseId} already associated with agent {agentId}:{agentVersion}, Updating it.')
        bedrock_agent.update_agent_knowledge_base(
            agentId=agentId,
            agentVersion=agentVersion,
            description=description,
            knowledgeBaseId=knowledgeBaseId,
            knowledgeBaseState=knowledgeBaseState
        )
    else:
        bedrock_agent.associate_agent_knowledge_base(
            agentId=agentId,
            agentVersion=agentVersion,
            description=description,
            knowledgeBaseId=knowledgeBaseId,
            knowledgeBaseState=knowledgeBaseState
        )

def create_agent_action_group(bedrock_agent, actionGroupName, description, 
                              actionGroupState, agentId, agentVersion,
                              apiSchema,agent_actions_lambda_arn):

    try:
        agents_ag_list = bedrock_agent.list_agent_action_groups(
                            agentId=agentId,
                            agentVersion=agentVersion
                        )
        existing_agent_ag = next((agent for agent in agents_ag_list['actionGroupSummaries']
                            if agent['actionGroupName'] == actionGroupName), None)
        actionGroupId = None
        if existing_agent_ag:
            actionGroupId = existing_agent_ag['actionGroupId']
            actionGroupName = existing_agent_ag['actionGroupName']
            print(f"Action group with name {actionGroupName} already exists. Will update and enable it") 
            bedrock_agent.update_agent_action_group(
                actionGroupExecutor={
                    'lambda': agent_actions_lambda_arn
                },
                actionGroupId=actionGroupId,
                actionGroupName=actionGroupName,
                actionGroupState='ENABLED',
                agentId=agentId,
                apiSchema=apiSchema,
                agentVersion=agentVersion
            )
        else:
            # Create agent
            print(f'Creating new agent action group with name {actionGroupName}')
            create_action_group_response = bedrock_agent.create_agent_action_group(
                actionGroupExecutor={
                    'lambda': agent_actions_lambda_arn
                },
                actionGroupName=actionGroupName,
                actionGroupState='ENABLED',
                agentId=agentId,
                apiSchema=apiSchema,
                agentVersion=agentVersion
            )
            actionGroupId = create_action_group_response['agentActionGroup']['actionGroupId']
        status_response = wait_for_completion(
            bedrock_agent,
            bedrock_agent.get_agent_action_group,
            {
                'actionGroupId': actionGroupId,
                'agentId':agentId,
                'agentVersion': agentVersion
            },
            'agentActionGroup.actionGroupState',
            ['ENABLED'],
            [],
            max_iterations=10,
            delay=2,
        )
        status = status_response['agentActionGroup']['actionGroupState']
        print(f"{'Updated' if existing_agent_ag else 'Created'} agent action group with name {actionGroupName} and current status {status}")
        return actionGroupId, status
    except ClientError as e:
        print(f"Error creating or retrieving agent: {e}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise    


def create_agent(bedrock_agent, agentName, agent_service_role_arn, 
                 description, foundation_model_id, agent_instruction, orchestrationType):

    try:
        agents_list = bedrock_agent.list_agents()
        existing_agent = next((agent for agent in agents_list['agentSummaries']
                            if agent['agentName'] == agentName), None)
        agent_id = None
        agent_arn = None
        if existing_agent:
            agent_id = existing_agent['agentId']
            agent_current_status = existing_agent['agentStatus']
            print(f"Using existing Agent with name {existing_agent['agentName']} and status {agent_current_status}")
            update_agent_response = bedrock_agent.update_agent(
                agentId=agent_id,
                agentName=agentName,
                agentResourceRoleArn=agent_service_role_arn,
                description=description,
                foundationModel=foundation_model_id,
                instruction=agent_instruction,
                orchestrationType=orchestrationType
            )
            agent_arn = update_agent_response['agent']['agentArn']
        else:
            # Create agent
            print(f'Creating new agent with name {agentName}')
            create_agent_response = bedrock_agent.create_agent(
                agentName=agentName,
                agentResourceRoleArn=agent_service_role_arn,
                description=description,
                foundationModel=foundation_model_id,
                instruction=agent_instruction,
                orchestrationType=orchestrationType
            )
            agent_id = create_agent_response['agent']['agentId']
            agent_arn = create_agent_response['agent']['agentArn']
        status_response = wait_for_completion(
            bedrock_agent,
            bedrock_agent.get_agent,
            {'agentId': agent_id},
            'agent.agentStatus',
            ['NOT_PREPARED', 'PREPARED'],
            ['FAILED'],
            max_iterations=10,
            delay=2,
        )
        status = status_response['agent']['agentStatus']
        version = status_response['agent'].get('agentVersion', None)
        print(f"{'Updated' if existing_agent else 'Created'} agent with name {agentName} and current status {status}")
        return agent_id, status, version, agent_arn
    except ClientError as e:
        print(f"Error creating or retrieving agent: {e}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise    

        
def create_knowledge_base(bedrock_agent, kb_name, 
                          kb_description, 
                          kb_role_arn,
                          embedding_model_arn,
                          vector_store_collection_arn,
                          vector_store_index_name):
    storage_configuration = {
        'opensearchServerlessConfiguration': {
            'collectionArn': vector_store_collection_arn,
            'fieldMapping': {
                'metadataField': 'text-metadata',
                'textField': 'text',
                'vectorField': 'vector'
            },
            'vectorIndexName': vector_store_index_name
        },
        "type": 'OPENSEARCH_SERVERLESS'
    }
    embedding_model_configuration = {
        "bedrockEmbeddingModelConfiguration": {
            "dimensions": 1024
        }
    }
    knowledge_base_configuration = {
        'type': 'VECTOR',
        'vectorKnowledgeBaseConfiguration': {
            'embeddingModelArn': embedding_model_arn,
            'embeddingModelConfiguration': embedding_model_configuration
        }
    }
    try:
        kb_list = bedrock_agent.list_knowledge_bases()
        existing_kb = next((kb for kb in kb_list['knowledgeBaseSummaries']
                            if kb['name'] == kb_name), None)
        if existing_kb:
            knowledge_base_id = existing_kb['knowledgeBaseId']
            kb_current_status = existing_kb['status']
            if kb_current_status != 'ACTIVE':
                raise Exception(f"Knowledge Base with name {existing_kb['name']} exists but is not in ACTIVE state. Knowledge Base state: {kb_current_status}")
            print(f"Using existing Knowledge Base with name {existing_kb['name']} and status {kb_current_status}")
            return knowledge_base_id, kb_current_status
        else:
            # Create knowledge base
            print(f'Creating new KB with name {kb_name}')
            create_kb_response = bedrock_agent.create_knowledge_base(
                description=kb_description,
                knowledgeBaseConfiguration=knowledge_base_configuration,
                name=kb_name,
                roleArn=kb_role_arn,
                storageConfiguration=storage_configuration
            )
            knowledge_base_id = create_kb_response['knowledgeBase']['knowledgeBaseId']
            status_response = wait_for_completion(
                bedrock_agent,
                bedrock_agent.get_knowledge_base,
                {'knowledgeBaseId': knowledge_base_id},
                'knowledgeBase.status',
                ['ACTIVE'],
                ['FAILED'],
                max_iterations=10,
                delay=10,
            )
            print(f"Created Knowledge Base with name {kb_name} and current status {status_response['knowledgeBase']['status']}")
            return knowledge_base_id, status_response['knowledgeBase']['status']
    except ClientError as e:
        print(f"Error creating or retrieving knowledge base: {e}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise


def create_data_source(bedrock_agent, knowledge_base_id, datasource_name='claims-eoc-datasource') :

    data_source_configuration = {
        'type': 'CUSTOM'
    }
    
    chunking_configuration = {
        'chunkingStrategy': 'HIERARCHICAL',
        'hierarchicalChunkingConfiguration': {
            'levelConfigurations': [
                {
                    'maxTokens': 1500
                },
                {
                    'maxTokens': 300
                },
            ],
            'overlapTokens': 60
        }
    }
    
    ds_list = bedrock_agent.list_data_sources(knowledgeBaseId=knowledge_base_id)
    existing_ds = next((ds for 
                               ds in ds_list['dataSourceSummaries']
                               if ds['name'] == datasource_name), None)
    if (existing_ds):
        existing_ds_id = existing_ds['dataSourceId']
        ds_current_status = existing_ds['status']
        if ds_current_status != 'AVAILABLE':
                raise Exception(f"Data source with name {existing_ds['name']} exists but is not in AVAILABLE state. Data source state: {ds_current_status}")
        print(f"Using existing Data source with name {existing_ds['name']} and status {ds_current_status}")
        return existing_ds_id, ds_current_status
    else:
        print(f"Creating new Data source with name {datasource_name}")
        create_ds_response = bedrock_agent.create_data_source(
            dataSourceConfiguration=data_source_configuration,
            description='direct injection of claims eoc documents',
            knowledgeBaseId=knowledge_base_id,
            name=datasource_name,
            vectorIngestionConfiguration={
                'chunkingConfiguration': chunking_configuration
            }
        )
        datasource_id = create_ds_response['dataSource']['dataSourceId']
        status_response = wait_for_completion(
            bedrock_agent,
            bedrock_agent.get_data_source,
            {'knowledgeBaseId': knowledge_base_id, 'dataSourceId': datasource_id},
            'dataSource.status',
            ['AVAILABLE'],
            ['FAILED'],
            max_iterations=5,
            delay=5,
        )
        print(f"Created datasource  with name {status_response['dataSource']['name']} and current status {status_response['dataSource']['status']}")        
        return datasource_id, status_response['dataSource']['status']
            

def ingest_and_wait(bedrock_agent, data_source_id , knowledge_base_id, documents):

    print("Ingesting documents...")
    bedrock_agent.ingest_knowledge_base_documents(
        dataSourceId=data_source_id,
        knowledgeBaseId=knowledge_base_id,
        documents=[
            get_document_configuration(document['document_id'], document['plan_name'], document['document_uri'])
            for document in documents
        ]
    )
    
    def wait_for_single_document(document):
        return wait_for_completion(
            client=bedrock_agent,
            get_status_function=bedrock_agent.get_knowledge_base_documents,
            status_kwargs={
                'dataSourceId': data_source_id,
                'knowledgeBaseId': knowledge_base_id,
                'documentIdentifiers': [{
                    'custom': {
                        'id': document['document_id']
                    },
                    'dataSourceType': 'CUSTOM'}]
            },
            completion_states=['INDEXED'],
            error_states=['FAILED'],
            status_path_in_response='documentDetails[0].status',
            max_iterations=5,
            delay=5, verbose=False
        )

    # Use ThreadPoolExecutor to run wait_for_completion in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all tasks
        future_to_document = {executor.submit(wait_for_single_document, document): document for document in documents}
        
        # Wait for all tasks to complete and collect results
        results = []
        for future in concurrent.futures.as_completed(future_to_document):
            document = future_to_document[future]
            try:
                result = future.result()
                result.update(document)
                results.append(result['documentDetails'][0])
            except Exception as exc:
                print(f"Document {document['document_id']} generated an exception: {exc}")
                results.append((document, None))
                raise
    print("Ingestion complete.")

    # Consolidate and return results
    return results


def add_lambda_permission(
    function_name,
    principal,
    action,
    source_arn=None,
    verbose = False
):
    lambda_client = boto3.client('lambda')
    try:
        statement_id_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        statement_id = f"claims-review-agent-actions-{statement_id_suffix}"
        kwargs = {
            'FunctionName': function_name,
            'StatementId': statement_id,
            'Action': action,
            'Principal': principal
        }
        # Add source_arn if provided
        if source_arn:
            kwargs['SourceArn'] = source_arn
        response = lambda_client.add_permission(**kwargs)
        print(f"Successfully added permission: {response}")
        return response
    except Exception as e:
        print(f"Error adding permission: {str(e)}")
        raise e


def invoke_agent_helper(bedrock_agent_runtime_client, query, 
                            session_id, agent_id, alias_id,
                            enable_trace=False, session_state=None):
        
    end_session: bool = False
    if not session_state:
        session_state = {}
    
    # Create main output widget for final answer
    final_answer_output = Output()
    
    # Create tab widget
    tab = Tab()
    tab_contents = []
    
    if enable_trace:
        display(final_answer_output)
        display(tab)
    
    def extract_trace_info(trace_event):
        """Helper function to extract relevant information from trace"""
        trace = trace_event.get('trace', {})
        orchestration_trace = trace.get('orchestrationTrace', {})
        model_invocation = orchestration_trace.get('modelInvocationInput', {})
        
        return {
            'Trace ID': model_invocation.get('traceId', ''),
            'Type': model_invocation.get('type', ''),
            'Text': model_invocation.get('text', '')
        }

    def create_trace_tab(trace_info):
        """Helper function to create a new tab for a trace"""
        output = Output()
        with output:
            df = pd.DataFrame([trace_info])
            display(HTML(f"""
            <style>
                table {{width: 100%; border-collapse: collapse;}}
                th, td {{padding: 8px; text-align: left; border: 1px solid #ddd;}}
                th {{background-color: #f2f2f2;}}
                tr:nth-child(even) {{background-color: #f9f9f9;}}
            </style>
            {df.to_html(escape=False, index=False)}
            """))
        return output

    # invoke the agent API
    agent_response = bedrock_agent_runtime_client.invoke_agent(
        inputText=query,
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        enableTrace=enable_trace,
        endSession=end_session,
        sessionState=session_state
    )

    event_stream = agent_response['completion']
    try:
        for event in event_stream: 
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer = data.decode('utf8')
                return agent_answer                
            elif 'trace' in event:
                if enable_trace:
                    trace_info = extract_trace_info(event.get('trace',{}))
                    if trace_info['Trace ID']:  # Only add if we have a valid trace
                        # Create new tab for this trace
                        new_tab = create_trace_tab(trace_info)
                        tab_contents.append(new_tab)
                        
                        # Update tab widget
                        tab.children = tuple(tab_contents)
                        # Set tab title
                        tab.set_title(len(tab_contents) - 1, f"Trace {len(tab_contents)}")
            else:
                raise Exception("unexpected event.", event)
    except Exception as e:
        raise Exception("unexpected event.", e)

