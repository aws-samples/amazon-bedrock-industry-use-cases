import boto3
import time
from crhelper import CfnResource

helper = CfnResource()

@helper.create
def create(event, context):
  print("No action needed on create")
  pass

@helper.update
def update(event, context):
  print("No action needed on update")
  pass

@helper.delete
def delete(event, context):
  try:
      # Extract the domain ID from the event
      domain_id = event['ResourceProperties']['DomainId']
      
      # Initialize AWS clients
      sagemaker = boto3.client('sagemaker')
      efs = boto3.client('efs')
      
      # Describe the domain to get EFS ID
      domain = sagemaker.describe_domain(DomainId=domain_id)
      efs_id = domain['HomeEfsFileSystemId']
      
      print(f'Deleting mount targets for EFS ID {efs_id}')
      # Delete mount targets

      try:
        mount_targets = efs.describe_mount_targets(FileSystemId=efs_id)['MountTargets']
        for mt in mount_targets:
          efs.delete_mount_target(MountTargetId=mt['MountTargetId'])
      
        # Wait for mount targets to be deleted with a check
        while True:
            print(f'Checking mount targets for EFS ID {efs_id}')
            response = efs.describe_mount_targets(FileSystemId=efs_id)
            if not response['MountTargets']:  # If no mount targets exist
                print('All mount targets deleted')
                break
            time.sleep(30)   # nosemgrep
        print(f'Deleting file system with EFS ID {efs_id}')
        # Delete the EFS file system
        efs.delete_file_system(FileSystemId=efs_id)
        print(f"Successfully deleted EFS {efs_id} for SageMaker Studio domain {domain_id}")
      except efs.exceptions.FileSystemNotFound:
        print(f"File system {efs_id} doesn't exist")
      except Exception:
        print(f"Error Deleting file System {efs_id}. Skipping")

      return efs_id
      
  except Exception as e:
      error_message = f"Error deleting EFS for SageMaker Studio domain {domain_id}: {str(e)}"
      print(error_message)
      raise Exception(error_message)

def lambda_handler(event, context):
  helper(event, context)