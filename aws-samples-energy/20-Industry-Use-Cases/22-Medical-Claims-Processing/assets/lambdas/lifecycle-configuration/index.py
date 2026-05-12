import boto3
import base64
from crhelper import CfnResource

helper = CfnResource()
client = boto3.client('sagemaker')

lcc_up1 = '\n'.join((
    '#!/bin/bash',
    '',
    'set -ex',
    '',
    'if [ ! -z "${SM_JOB_DEF_VERSION}" ]',
    'then',
    '   echo "Running in job mode, skip lcc"',
    'else',
    '   rm -rf amazon-bedrock-samples',
    '   git clone https://github.com/aws-samples/sample-document-processing-with-amazon-bedrock-data-automation.git',
    '   mv sample-document-processing-with-amazon-bedrock-data-automation  bda-workshop',
    '   rm -rf sample-document-processing-with-amazon-bedrock-data-automation',
    '   echo "Repo cloned from git"',
    'fi',
    '',
))

def get_lcc_base64_string(lcc_string):
    lcc_bytes = lcc_string.encode("ascii")
    base64_lcc_bytes = base64.b64encode(lcc_bytes)
    base64_lcc_string = base64_lcc_bytes.decode("ascii")
    return base64_lcc_string

def apply_lcc_to_user_profile(base64_lcc_string, lcc_config_name, profile):
    response = client.create_studio_lifecycle_config(
        StudioLifecycleConfigName=lcc_config_name,
        StudioLifecycleConfigContent=base64_lcc_string,
        StudioLifecycleConfigAppType="JupyterLab",
    )

    lcc_arn = response["StudioLifecycleConfigArn"]
    update_up = client.update_user_profile(
        DomainId=profile.split("|")[1],
        UserProfileName=profile.split("|")[0],
        UserSettings={
            "JupyterLabAppSettings": {
                "DefaultResourceSpec": {"LifecycleConfigArn": lcc_arn},
                "LifecycleConfigArns": [lcc_arn]
            }
        }
    )
    return update_up

@helper.create
@helper.update
def create_or_update(event, context):
    up1 = event["ResourceProperties"]["UserProfile"]
    lcc_name_up1 = event["ResourceProperties"]["LCCName"]
    try:
        if event["RequestType"] == "Update":
            try:
                response1 = client.delete_studio_lifecycle_config(
                    StudioLifecycleConfigName=lcc_name_up1
                )
                print(response1)
            except Exception as e2:
                print(e2)
        
        base64_lcc_up1_string = get_lcc_base64_string(lcc_up1)
        updated_up1 = apply_lcc_to_user_profile(
            base64_lcc_up1_string,
            lcc_name_up1,
            up1
        )
        print("Response User Profile LCC update for UP1")
        print(updated_up1)
        
        return {"Data": 120}
    except Exception as e:
        raise e

@helper.delete
def delete(event, context):
    lcc_name_up1 = event["ResourceProperties"]["LCCName"]

    try:
        response1 = client.delete_studio_lifecycle_config(
            StudioLifecycleConfigName=lcc_name_up1
        )
        print(response1)
        return {}
    except Exception as e:
        print(e)
        return {"Error": str(e)}

def lambda_handler(event, context):
    print(event)
    helper(event, context)
