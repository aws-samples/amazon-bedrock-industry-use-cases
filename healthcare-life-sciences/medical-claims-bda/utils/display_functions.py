import ipywidgets as widgets
from IPython.display import display
import boto3


s3 = boto3.client('s3')


def get_view(data, display_function=None):
    out = widgets.Output()
    with out:
        if callable(display_function):
            display_function(data)
        else:
            display(data)
    return out

def display_multiple(views, view_titles = None):
    main_tab = widgets.Tab()
    for i, view in enumerate(views):
        main_tab.children = (*main_tab.children, view)
        tab_title = view_titles[i] if view_titles and view_titles[i] else f'Document {i}'
        main_tab.set_title(i, title=tab_title)
    display(main_tab)