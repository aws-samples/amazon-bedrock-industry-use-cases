import json
import ipywidgets as widgets
import io


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


def get_s3_to_dict(s3, s3_url):
    bucket_name = s3_url.split('/')[2]
    object_key = '/'.join(s3_url.split('/')[3:])
    
    # Download the JSON file from S3
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    json_content = response['Body'].read().decode('utf-8')
    
    # Parse the JSON content
    json_obj = json.loads(json_content)
    return json_obj