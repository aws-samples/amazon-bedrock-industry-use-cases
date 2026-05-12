import ipywidgets as widgets
from IPython.display import display, HTML
import pandas as pd
from PIL import Image
import io
import boto3
from urllib.parse import urlparse
from pdf2image import convert_from_bytes


s3 = boto3.client('s3')


onclick_function = """
<script>
    function handleClick(event) {
    
        var row = event.target
        row.style.backgroundColor = '#e0e0e0';
        if (!row) return;  // Click wasn't on a row
        
        // Get the bbox data from the row
        var bbox = row.getAttribute('data-bbox');
        if (!bbox) return;  // No bbox data found
        
        // Parse the bbox string back to array
        bbox = JSON.parse(bbox);
        
        // Send custom event to Python
        var event = new CustomEvent('bbox_click', { detail: bbox });
        document.dispatchEvent(event);
        
        // Highlight the clicked row
        var rows = document.getElementsByClassName('bbox-row');
        for(var i = 0; i < rows.length; i++) {
            rows[i].style.backgroundColor = '#f8f8f8';
        }
        row.style.backgroundColor = '#e0e0e0';
    }
</script>
"""

def load_image(uri):
    if uri.startswith('s3://'):
        bucket, key = urlparse(uri).netloc, urlparse(uri).path.lstrip('/')
        file_content = s3.get_object(Bucket=bucket, Key=key)['Body'].read()
    else:
        file_content = open(uri, 'rb').read()
    
    if uri.lower().endswith('.pdf'):
        img_io = io.BytesIO()
        convert_from_bytes(file_content)[0].save(img_io, format='JPEG')
        return img_io.getvalue()
    
    img = Image.open(io.BytesIO(file_content))
    if img.format != 'JPEG':
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        return img_io.getvalue()
    return file_content
    

def get_kv_html(kv_pairs):
    # Create key-value pairs display
    kv_html = onclick_function
    kv_html += """
    <div style="border: 0px solid #ddd; padding: 10px; margin: 1px; overflow-y: auto;">        
        <table style="width: 100%; border: 0px solid #888; border-collapse: separate; border-spacing: 1 1px;">
            <style>
                td {
                    padding: 2px 2px;
                    border: 0px solid #ddd; 
                }
            </style>
    """
    
    for i, (key, (value, confidence)) in enumerate(kv_pairs.items()):
        kv_html += '<tr onclick=handleClick(event) data-bbox=\'(10,40,110,200)\'><td width=100%>'
        kv_html += create_key_value_box(key, value, confidence)
        kv_html += '</td></tr>'
    kv_html += """
        </table>
    </div>
    """
    return kv_html

def create_key_value_box(key, value, confidence):
    html = f"""
       <div style="
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 2px;
            margin: 2px 1;
            background-color: #f8f9fa;
            width: 100%;
            max-width: 100%;
            font-family: sans-serif;"
        >
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0px;
        ">
            <div style="font-weight: 600; font-size: 0.9em; color: #333;">{key}</div>
            <div style="
                background-color: #fff;
                padding: 2px 4px;
                border-radius: 4px;
                font-size: 0.9em;
                color: #666;
            ">{confidence}</div>
        </div>
        <div style="color: #666; font-size: 0.9em">{value}</div>
    </div>
    """
    return html
    
def display_result(document_image_uri, kvpairs):
    # Create the layout with top alignment
    main_hbox_layout = widgets.Layout(
        width='100%',
        display='flex',
        flex_flow='row nowrap',
        align_items='stretch',
        margin='0'
    )

    image_widget = widgets.Image(
        value=b'',
        format='png',
        width='auto',
        height='auto'
    )
    image_widget.value = load_image(image_path=document_image_uri)
    image_container = widgets.Box(
        children=[image_widget],
        layout=widgets.Layout(
            border='1px solid #888',
            padding='1px',
            margin='2px',
            width='70%',
            flex='0 0 70%',
            min_width='300px',
            height='auto',
            display='flex',
            align_items='stretch',
            justify_content='center'
        )
    )
    kv_html = get_kv_html(kvpairs)
    # Add content to the Forms tab
    result_widget = widgets.HTML(
        value=kv_html,
        layout=widgets.Layout(
            border='0px solid #888',            
            width='100%', 
            height='10px',
            flex='0 0 100%',       # flex: grow shrink basis
            margin='5px',
            min_width='300px'
        )
    )
    result_container = widgets.VBox(
        children=[result_widget],
        layout=widgets.Layout(
            border='0px solid #888',
            padding='4px',
            margin='5px',
            width='30%',
            flex='0 0 30%',
            min_width='200px',
            justify_content='center'
        )
    )
    # Add custom CSS for scrollable container
    custom_style = """
    <style>
        .scrollable-vbox {
            max-height: 1000px;
            overflow-y: auto;
            overflow-x: hidden;
        }
        .main-container {
            display: flex;
            height: 1000px;  /* Match with max-height above */
        }
    </style>
    """
    display(HTML(custom_style))
    # Create the main layout
    main_layout = widgets.HBox(
        children=[image_container, result_container],
        layout=main_hbox_layout
    )
    # Add the scrollable class to the right VBox
    result_widget.add_class('scrollable-vbox')
    main_layout.add_class('main-container')
    # Display the main layout
    display(main_layout)

def display_multiple(views, view_titles = None):
    main_tab = widgets.Tab()
    for i, view in enumerate(views):
        main_tab.children = (*main_tab.children, view)
        tab_title = view_titles[i] if view_titles and view_titles[i] else f'Document {i}'
        main_tab.set_title(i, title=tab_title)
    display(main_tab)

def create_form_view(forms_data):

    styles = """
    <style>
        .kv-container{display:flex;flex-direction:column;gap:4px;margin:4px;width:100%}
        .kv-box{border:0px solid #e0e0e0;border-radius:4px;padding:4px;margin:0;background-color:#f8f9fa;width:auto}
        .kv-item{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}
        .kc-item{background-color:#fff;display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}
        .key{font-weight:600;padding:1px 4px;font-size:.85em;color:#333}
        .value{background-color:#fff;padding:1px 4px;border-radius:4px;font-size:.85em;color:#666;margin-top:1px}
        .confidence{padding:1px 4px;border-radius:4px;font-size:.85em;color:#2196F3}
        .nested-container{margin-left:8px;margin-top:4px;border-left:2px solid #e0e0e0;padding-left:4px}
        .parent-key{color:#6a1b9a;font-size:.9em;font-weight:600;margin-bottom:2px}
    </style>
    """

    def render_nested_keys(data):
        if not isinstance(data, dict): 
            return f'<div class="value">{data}</div>'
        html = ""
        for key, value in data.items():
            if isinstance(value, dict) and 'value' in value:
                conf = value.get('confidence', 0) * 100
                html += f"""
                    <div class='kv-box'>
                        <div class='kv-item'><div class='key'>{key}</div></div>
                        <div class='kc-item' onclick=handleClick(event) data-bbox='(10,40,110,200)'>
                            <div class="value">{value['value']}</div>
                            <div class='confidence'>{conf:.1f}%</div>
                        </div>
                    </div>"""
            else:
                html += f"""
                    <div class='kv-box'>
                        <div class='kv-item'><div class='key'>{key}</div></div>
                        <div class="nested-container">{render_nested_keys(value)}</div>
                    </div>"""
        return html

    return HTML(f"{styles}<script>function handleClick(e){{console.log(e.currentTarget.dataset.bbox)}}</script><div class='kv-container'>{render_nested_keys(forms_data)}</div>")


def create_table_view(tables_data):
    styles = """
    <style>
        .table-wrapper {
            width: 100%;
            overflow-x: auto;
            white-space: nowrap;
            -webkit-overflow-scrolling: touch;
        }
        .table-container{margin:20px}
        .table-view{
            width: auto;
            min-width: 100%;
            border-collapse:collapse;
            background-color:white;
            table-layout: auto;
        }
        .table-view th{
            background-color:#f8f9fa;
            padding:12px;
            text-align:left;
            font-size:0.85em;
            border:1px solid #dee2e6;
            white-space: nowrap;
        }
        .table-view td{
            padding:12px;
            border:1px solid #dee2e6;
            font-size:0.8em;
            white-space: nowrap;
        }
        .confidence{color:#2196F3;font-size:0.9em}
    </style>
    """
    
    def process_table(table_data):
        def format_cell(cell):
            if isinstance(cell, dict) and 'value' in cell:
                conf = f"<span class='confidence'>({cell.get('confidence', 0):.1%})</span>" if 'confidence' in cell else ""
                return f"{cell['value']}{conf}"
            return str(cell)
        
        return pd.DataFrame([{k: format_cell(v) for k, v in row.items()} for row in table_data])
    
    tables_html = "".join(
        f"""
        <div class="table-container">
            <h3>{table_name}</h3>
            <div class="table-wrapper">
                {process_table(table_data).to_html(classes='table-view', index=False, escape=False)}
            </div>
        </div>
        """
        for table_name, table_data in tables_data.items() if table_data
    )
    
    return HTML(f"{styles}{tables_html}")

def segment_view(document_image_uris, inference_result):
    # Create the layout with top alignment
    main_hbox_layout = widgets.Layout(
        width='100%',
        display='flex',
        flex_flow='row nowrap',
        align_items='stretch',
        margin='0'
    )
    image_widget = widgets.Image(
        value=b'',
        format='png',
        width='auto',
        height='auto'
    )
    image_widget.value = load_image(uri=document_image_uris[0])
    image_container = widgets.VBox(
        children=[image_widget],
        layout=widgets.Layout(
            border='0px solid #888',
            padding='1px',
            margin='2px',
            width='60%',
            flex='0 0 60%',
            min_width='300px',
            height='auto',
            display='flex',
            align_items='stretch',
            justify_content='center'
        )
    )
    
    
    # Create tabs for different views
    tab = widgets.Tab(
        layout=widgets.Layout(
            width='40%',
            flex='0 0 40%',
            min_width='300px',
            height='auto'
        )
    )
    form_view = widgets.Output()
    table_view = widgets.Output()
    
    with form_view:
        display(create_form_view(inference_result['forms']))
        
    with table_view:
        display(create_table_view(inference_result['tables']))
    
    tab.children = [form_view, table_view]
    tab.set_title(0, 'Key Value Pairs')
    tab.set_title(1, 'Tables')

    
    # Add custom CSS for scrollable container
    custom_style = """
    <style>
        .scrollable-vbox {
            max-height: 1000px;
            overflow-y: auto;
            overflow-x: hidden;
        }
        .main-container {
            display: flex;
            height: 1000px;  /* Match with max-height above */
        }
        .jupyter-widgets-output-area .p-TabBar-tab {
            min-width: fit-content !important;
            max-width: fit-content !important;
            padding: 6px 10px !important;
    </style>
    """
    display(HTML(custom_style))
    
    # Create the main layout
    main_layout = widgets.HBox(
        children=[image_container, tab],
        layout=main_hbox_layout
    )

    
    # Add the scrollable class to the right VBox
    main_layout.add_class('main-container')
    return main_layout


def get_view(data, display_function=None):
    out = widgets.Output()
    with out:
        if callable(display_function):
            display_function(data)
        else:
            display(data)
    return out