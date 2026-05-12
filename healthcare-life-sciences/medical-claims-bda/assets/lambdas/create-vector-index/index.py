import boto3
from crhelper import CfnResource
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from time import sleep


helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)

#No-op for update and delete
@helper.delete
def no_op(event, context):
    print("No op for delete")

#get aoss_host from os environ
def removeHttpsPrefix(endpoint):
    """
    This function removes the "https://" prefix from a given endpoint string,
    if present, and returns the modified string.
    """
    if endpoint.startswith("https://"):
        return endpoint[8:]
    return endpoint

def get_aoss_host(resource_properties):
    if "AOSSHost" not in resource_properties:
        raise Exception("AOSSHost not provided from resource properties")

    return removeHttpsPrefix(resource_properties["AOSSHost"])

def get_aoss_client(host):
    auth = AWSV4SignerAuth(
        boto3.Session().get_credentials(), 
        boto3.session.Session().region_name,
        "aoss"
    )
    # create an opensearch client and use the request-signer
    return OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
def get_aoss_index_name(resource_properties):
    if "AOSSIndexName" not in resource_properties:
        raise Exception("AOSSIndexName not provided from resource properties")
    return resource_properties["AOSSIndexName"]
        
#Function to use the opensearch-py library to create an index within an opensearch collection
def create_aoss_index(index_name, aos_client):
    index_body = {
        "settings": {
            "index.knn": True
        },
        "mappings": {
            "properties": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "l2",
                        "engine": "faiss",
                        "parameters": {
                            "ef_construction": 512,
                            "m": 16
                        }
                    }
                },
                "text": {
                    "type": "text"
                },
                "id": {
                    "type": "text"
                },
                "text-metadata": {
                    "type": "text"
                },
                "x-amz-bedrock-kb-source-uri": {
                    "type": "text"
                }
            }
        }
    }              

    aos_client.indices.create(index=index_name, body=index_body)
    print(f"Created index {index_name}")
    
#Handles create event of the CloudFormation resource
@helper.create
@helper.update
def create_or_update_index(event, context):
    resource_properties = event['ResourceProperties']
    aoss_host = get_aoss_host(resource_properties)
    aos_client = get_aoss_client(aoss_host)
    index_name = get_aoss_index_name(resource_properties)
    response = None
    sleep(60)   # nosemgrep
    if not aos_client.indices.exists(index=index_name):
        response = create_aoss_index(index_name=index_name, aos_client=aos_client)
    return response

def lambda_handler(event, context):
    print(event)
    helper(event, context)