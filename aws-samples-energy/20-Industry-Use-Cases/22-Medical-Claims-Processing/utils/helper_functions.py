import os
import time
import boto3
from urllib.parse import urlparse
import requests
import base64
import io
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from botocore.exceptions import ClientError
from IPython.display import HTML
from IPython.display import display
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import json
import ipywidgets as widgets
import html
import pandas as pd

s3_client = boto3.client("s3")
bda_client = boto3.client('bedrock-data-automation')
bda_runtime_client = boto3.client('bedrock-data-automation-runtime')
cfn = boto3.client(service_name='cloudformation')
region_name = boto3.session.Session().region_name
# Dictionary to store the outputs
resource_attributes = {}
target_output_key = 'BDAWorkshopVPC'

def get_stack_outputs():
    # Initialize CloudFormation client
    cf_client = boto3.client('cloudformation', region_name=region_name)
    try:
        # Get all stacks
        paginator = cf_client.get_paginator('list_stacks')
        for page in paginator.paginate(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']):
            for stack in page['StackSummaries']:
                stack_name = stack['StackName']
                # Get stack details including outputs
                try:
                    response = cf_client.describe_stacks(StackName=stack_name)
                    # Check if stack has outputs
                    if 'Outputs' in response['Stacks'][0]:
                        outputs = response['Stacks'][0]['Outputs']
                        # Look for target OutputKey
                        if any(output['OutputKey'] == target_output_key 
                               for output in outputs):
                            # Found the stack with target OutputKey, get all its outputs
                            for output in outputs:
                                resource_attributes[output['OutputKey']] = output['OutputValue']
                            return resource_attributes
                except cf_client.exceptions.ClientError as e:
                    print(f"Error describing stack {stack_name}: {str(e)}")
                    continue
        print(f"No stack found with OutputKey: {target_output_key}")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def get_stack_output(stack_name, output_key):
    response = cfn.describe_stacks( StackName=stack_name)
    stack = next((s for s in response['Stacks'] if s['StackName'] == stack_name), None)
    return next((o['OutputValue'] for o in stack['Outputs'] if o['OutputKey'] == output_key), None) if stack else None


def pil_to_bytes(image):
    byte_arr = io.BytesIO()
    image.save(byte_arr, format='PNG')
    return byte_arr.getvalue()


def display_image(image):
    image_widget = widgets.Image(value=pil_to_bytes(image), format='png')
    image_widget.layout.width = '400px'
    image_widget.layout.height = 'auto'
    image_widget.layout.object_fit = 'contain'
    return image_widget

def json_to_html(json_obj, indent=0):
    result = []
    if isinstance(json_obj, dict):
        result.append('<table class="json-object">')
        for key, value in json_obj.items():
            result.append('<tr>')
            result.append(f'<td class="key">{key}</td>')
            result.append('<td class="value">')
            result.append(json_to_html(value, indent + 1))
            result.append('</td>')
            result.append('</tr>')
        result.append('</table>')
    elif isinstance(json_obj, list):
        result.append('<table class="json-array">')
        for i, item in enumerate(json_obj):
            result.append('<tr>')
            result.append(f'<td class="key">{i}</td>')
            result.append('<td class="value">')
            result.append(json_to_html(item, indent + 1))
            result.append('</td>')
            result.append('</tr>')
        result.append('</table>')
    elif isinstance(json_obj, (str, int, float, bool)) or json_obj is None:
        if isinstance(json_obj, str):
            result.append(f'<span class="string">"{json_obj}"</span>')
        elif isinstance(json_obj, bool):
            result.append(f'<span class="boolean">{str(json_obj).lower()}</span>')
        elif json_obj is None:
            result.append('<span class="null">null</span>')
        else:
            result.append(f'<span class="number">{json_obj}</span>')
    return ''.join(result)
    
def display_json(json_data, title):
    html_content = f"""
    <div class="json-container">
        <h3 class="json-title">{title}</h3>
        <div class="json-viewer">
            {json_to_html(json_data)}
        </div>
    </div>
    <style>
        .json-container {{
            margin-bottom: 20px;
        }}
        .json-title {{
            font-family: sans-serif;
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }}
        .json-viewer {{
            font-family: monospace;
            font-size: 14px;
            line-height: 1.5;
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            max-height: 500px;
            overflow: auto;
        }}
        .json-object, .json-array {{
            border-collapse: collapse;
            margin-left: 20px;
        }}
        .key {{
            color: #881391;
            vertical-align: top;
            padding-right: 10px;
        }}
        .value {{
            padding-left: 10px;
        }}
        .string {{ color: #1a1aa6; }}
        .number {{ color: #116644; }}
        .boolean {{ color: #ff8c00; }}
        .null {{ color: #808080; }}
    </style>
    """
    return widgets.HTML(html_content)

def display_image_jsons(image, json_arr, titles):
    image_widget = display_image(image)
    right_column =  widgets.VBox([display_json(data, title) for data, title in zip(json_arr, titles)])
    bordered_hbox = widgets.HBox([image_widget, right_column])
    bordered_hbox.layout.border = '5px solid black'
    bordered_hbox.layout.padding = '10px'
    bordered_hbox.layout.margin = '10px'
    return bordered_hbox

def get_bucket_and_key(s3_uri):
    parsed_uri = urlparse(s3_uri)
    bucket_name = parsed_uri.netloc
    object_key = parsed_uri.path.lstrip('/')
    return (bucket_name, object_key)

def wait_for_job_to_complete(invocationArn):
    get_status_response = bda_runtime_client.get_data_automation_status(
         invocationArn=invocationArn)
    status = get_status_response['status']
    job_id = invocationArn.split('/')[-1]
    max_iterations = 60
    iteration_count = 0
    while status not in ['Success', 'ServiceError', 'ClientError']:
        print(f'Waiting for Job to Complete. Current status is {status}')
        # Wait for kernel restart
        time.sleep(10) # nosemgrep
        iteration_count += 1
        if iteration_count >= max_iterations:
            print(f"Maximum number of iterations ({max_iterations}) reached. Breaking the loop.")
            break
        get_status_response = bda_runtime_client.get_data_automation_status(
         invocationArn=invocationArn)
        status = get_status_response['status']
    if iteration_count >= max_iterations:
        raise Exception("Job did not complete within the expected time frame.")
    else:
        print(f"Invocation Job with id {job_id} completed. Status is {status}")
    return get_status_response


def read_s3_object(s3_uri):
    # Parse the S3 URI
    parsed_uri = urlparse(s3_uri)
    bucket_name = parsed_uri.netloc
    object_key = parsed_uri.path.lstrip('/')
    # Create an S3 client
    s3_client = boto3.client('s3')
    try:
        # Get the object from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        
        # Read the content of the object
        content = response['Body'].read().decode('utf-8')
        return content
    except Exception as e:
        print(f"Error reading S3 object: {e}")
        return None

def download_document(url, start_page_index=None, end_page_index=None, output_file_path=None):

    if not output_file_path:
        filename = os.path.basename(url)
        output_file_path = filename
        
    # Download the PDF
    response = requests.get(url, timeout=30) # nosemgrep
    print(response)
    pdf_content = io.BytesIO(response.content)
    
    # Create a PDF reader object
    pdf_reader = PdfReader(pdf_content)
    
    # Create a PDF writer object
    pdf_writer = PdfWriter()
    
    start_page_index = 0 if not start_page_index else max(start_page_index,0)
    end_page_index = len(pdf_reader.pages)-1 if not end_page_index else min(end_page_index,len(pdf_reader.pages)-1)

    # Specify the pages you want to extract (0-indexed)
    pages_to_extract = list(range(start_page_index, end_page_index))
    
    # Add the specified pages to the writer
    for page_num in pages_to_extract:
        page = pdf_reader.pages[page_num]
        pdf_writer.add_page(page)

    print(f"Created file: {output_file_path}")
    # Save the extracted pages to a new PDF
    with open(output_file_path, "wb") as output_file:
        pdf_writer.write(output_file)
    return output_file_path


def create_image_html_column(row: pd.Series, image_col: str, width: str = '300px') -> str:
    """
    Create HTML embedded image from S3 URI by downloading and base64 encoding the image for a DataFrame row.
    
    Args:
        row (pd.Series): DataFrame row
        image_col (str): Name of column containing S3 URI
        width (str): Fixed width for image
        
    Returns:
        str: HTML string for embedded image
    """
    s3_uri = row[image_col]
    if isinstance(s3_uri, list):
        s3_uri = s3_uri[0]    
    if pd.isna(s3_uri):
        return ''
    
    try:
        # Parse S3 URI
        bucket_name, object_key = get_bucket_and_key(s3_uri)

        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # Download image from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        image_content = response['Body'].read()
        
        # Open image using PIL
        image = Image.open(io.BytesIO(image_content))
        
        # Convert image to RGB if it's in RGBA mode
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        
        # Save image to bytes
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        
        # Encode image to base64
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Create HTML string with base64 encoded image
        return f'<img src="data:image/jpeg;base64,{img_str}" style="width: {width}; object-fit: contain;">'
    except Exception as e:
        print(f"Error processing image {s3_uri}: {str(e)}")
        return ''

# Example usage:
"""
# Add embedded images column
df['embedded_images'] = add_embedded_images(df, 'crop_images', width='300px')

# For Jupyter notebook display:
from IPython.display import HTML
HTML(df['embedded_images'].iloc[0])
"""



def wait_for_completion(
    client,
    get_status_function,
    status_kwargs,
    status_path_in_response,
    completion_states,
    error_states,
    max_iterations=60,
    delay=10,
    verbose=True
):
    for _ in range(max_iterations):
        try:
            response = get_status_function(**status_kwargs)
            status = get_nested_value_new(response, status_path_in_response)

            if status in completion_states:
                if(verbose):
                    print(f"Operation completed successfully with status: {status}")
                return response

            if status in error_states:
                raise Exception(f"Operation failed with status: {status}")
            if(verbose):
                print(f"Current status: {status}. Waiting...")
            time.sleep(delay) # nosemgrep

        except ClientError as e:
            raise Exception(f"Error checking status: {str(e)}")

    raise Exception(f"Operation timed out after {max_iterations} iterations")

def get_nested_value_new(data, path):
    """Get value from nested dict/list using dot path with array support (e.g., 'items[0].name')"""
    current = data
    try:
        for part in path.replace('[', '.[').split('.'):
            if not part: 
                continue
            if '[' in part:
                name, index = part.split('[')
                current = current[name] if name else current
                current = current[int(index.rstrip(']'))]
            else:
                current = current[part]
        return current
    except (KeyError, IndexError, TypeError, ValueError):
        return None

def get_nested_value(data, path):
    """
    Retrieve a value from a nested dictionary using a dot-separated path.

    :param data: The dictionary to search
    :param path: A string representing the path to the value, e.g., "Job.Status"
    :return: The value at the specified path, or None if not found
    """
    keys = path.split('.')
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return None
    return data


def display_html(data, root='root', expanded=True, bg_color='#f0f0f0'):
    html = f"""
        <div class="custom-json-output" style="background-color: {bg_color}; padding: 10px; border-radius: 5px;">
            <button class="toggle-btn" style="margin-bottom: 10px;">{'Collapse' if expanded else 'Expand'}</button>
            <pre class="json-content" style="display: {'block' if expanded else 'none'};">{data}</pre>
        </div>
        <script>
        (function() {{
            var toggleBtn = document.currentScript.previousElementSibling.querySelector('.toggle-btn');
            var jsonContent = document.currentScript.previousElementSibling.querySelector('.json-content');
            toggleBtn.addEventListener('click', function() {{
                if (jsonContent.style.display === 'none') {{
                    jsonContent.style.display = 'block';
                    toggleBtn.textContent = 'Collapse';
                }} else {{
                    jsonContent.style.display = 'none';
                    toggleBtn.textContent = 'Expand';
                }}
            }});
        }})();
        </script>
        """
    display(HTML(html))

def send_request(region, url, method, credentials, payload=None, service='bedrock'):
    host = url.split("/")[2]
    request = AWSRequest(
            method,
            url,
            data=payload,
            headers={'Host': host, 'Content-Type':'application/json'}
    )    
    SigV4Auth(credentials, service, region).add_auth(request)
    response = requests.request(method, url, headers=dict(request.headers), data=payload, timeout=50)
    response.raise_for_status()
    content = response.content.decode("utf-8")
    data = json.loads(content)
    return data

def invoke_blueprint_recommendation_async(bda_client, payload):
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    region_name = boto3.Session().region_name
    url = f"{bda_client.meta.endpoint_url}/invokeBlueprintRecommendationAsync"
    print(f'Sending request to {url}')
    result = send_request(
        region = region_name,
        url = url,
        method = "POST", 
        credentials = credentials,
        payload=payload
    )
    return result


def get_blueprint_recommendation(bda_client, job_id):
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    region_name = boto3.Session().region_name
    url = f"{bda_client.meta.endpoint_url}/getBlueprintRecommendation/{job_id}/"
    result = send_request(
        region = region_name,
        url = url,
        method = "POST",
        credentials = credentials        
    )
    return result

def get_s3_to_dict(s3_url):
    bucket_name = s3_url.split('/')[2]
    object_key = '/'.join(s3_url.split('/')[3:])
    
    # Download the JSON file from S3
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    json_content = response['Body'].read().decode('utf-8')
    
    # Parse the JSON content
    json_obj = json.loads(json_content)
    return json_obj

def create_or_update_blueprint(bda_client, blueprint_name, blueprint_description, blueprint_type, blueprint_stage, blueprint_schema):
    list_blueprints_response = bda_client.list_blueprints(
        blueprintStageFilter='ALL'
    )
    blueprint = next((blueprint for blueprint in
                      list_blueprints_response['blueprints']
                      if 'blueprintName' in blueprint and
                      blueprint['blueprintName'] == blueprint_name), None)
    response = None
    if not blueprint:
        print(f'No existing blueprint found with name={blueprint_name}, creating custom blueprint')
        response = bda_client.create_blueprint(
            blueprintName=blueprint_name,
            type=blueprint_type,
            blueprintStage=blueprint_stage,
            schema=json.dumps(blueprint_schema)
        )
    else:
        print(f'Found existing blueprint with name={blueprint_name}, updating Stage and Schema')
        response = bda_client.update_blueprint(
            blueprintArn=blueprint['blueprintArn'],
            blueprintStage=blueprint_stage,
            schema=json.dumps(blueprint_schema)
        )

    return response['blueprint']['blueprintArn']


def transform_custom_output(input_json, explainability_info):
    result = {
        "forms": {},
        "tables": {}
    }

    def add_confidence(value, conf_info):
        return {"value": value, "confidence": conf_info["confidence"]} if isinstance(conf_info, dict) and "confidence" in conf_info else value
    
    def process_list_item(item, conf_info):
        return {k: add_confidence(v, conf_info.get(k, {})) for k, v in item.items() if isinstance(conf_info, dict)}    

    # Iterate through the input JSON
    for key, value in input_json.items():
        confidence_data = explainability_info.get(key, {})
        if isinstance(value, list):
            # Handle lists (tables)
            processed_list = []
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    # Process each item in the list using its corresponding confidence info
                    conf_info = confidence_data[idx] if isinstance(confidence_data, list) else confidence_data
                    processed_list.append(process_list_item(item, conf_info))
            result["tables"][key] = processed_list
        else:
            # Handle simple key-value pairs (forms)
            result["forms"][key] = add_confidence(value, confidence_data)
            
    return result


def get_summaries(custom_outputs):
    return [{
        'page_indices': output.get('split_document', {}).get('page_indices'),
        'matched_blueprint_name': output.get('matched_blueprint', {}).get('name'),
        'confidence': output.get('matched_blueprint', {}).get('confidence'),
        'document_class_type': output.get('document_class', {}).get('type')
    } if output else {} for output in custom_outputs]

def show_popup_link(label, content, unique_id):
    # Create HTML with CSS and JavaScript
    html_content = f"""
    <style>
    .orange-button {{
        background-color: #FF9800;
        border: none;
        color: white;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 4px;
        transition: background-color 0.3s;
    }}
    
    .orange-button:hover {{
        background-color: #F57C00;
    }}
    
    .modal {{
        display: none;
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        bottom:10px;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.4);
        justify-content: center;  # Added
        padding-top: 50px;
    }}
    
    .modal-content {{
        background-color: #fefefe;
        margin: 5% auto;
        padding: 10px;
        border: 1px solid #888;
        width: 80%;
        max-height: 70vh;
        overflow-y: auto;
        position: relative;
    }}
    
    .close-btn {{
        color: #aaa;
        float: right;
        font-size: 28px;
        font-weight: bold;
        cursor: pointer;
    }}
    
    .close-btn:hover {{
        color: black;
    }}
    </style>
    
    <button class="orange-button" onclick="showModal_{unique_id}()">{label}</button>
    
    <div id="instructionModal_{unique_id}" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal_{unique_id}()">&times;</span>
            <pre>{html.escape(content)}</pre>
        </div>
    </div>
    
    <script>
        function showModal_{unique_id}() {{
            document.getElementById("instructionModal_{unique_id}").style.display = "block";
        }}
        
        function closeModal_{unique_id}() {{
            document.getElementById("instructionModal_{unique_id}").style.display = "none";
        }}
        
        // Close modal when clicking outside of it
        window.onclick = function(event) {{
            var modal = document.getElementById("instructionModal_{unique_id}");
            if (event.target == modal) {{
                modal.style.display = "none";
            }}
        }}
        
        // Close modal when pressing Escape key
        document.addEventListener('keydown', function(event) {{
            if (event.key === "Escape") {{
                document.getElementById("instructionModal_{unique_id}").style.display = "none";
            }}
        }});

    </script>
    """
    
    display(HTML(html_content))
    
        
