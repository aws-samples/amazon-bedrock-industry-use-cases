FROM public.ecr.aws/lambda/python:3.10.2024.03.04.10-x86_64

# Installs python, removes cache file to make things smaller
RUN yum update -y && \
    yum install -y python3 python3-dev python3-pip gcc && \
    rm -Rf /var/cache/yum

# Copies requirements.txt file into the container
COPY requirements.txt ./
# Installs dependencies found in your requirements.txt file
RUN pip install -r requirements.txt

# Be sure to copy over the function itself!
# Goes last to take advantage of Docker caching.
COPY index_custom_resource.py ./

# Points to the handler function of your lambda function
CMD ["index_custom_resource.on_event"]