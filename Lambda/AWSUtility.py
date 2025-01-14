import logging
import time
from botocore.exceptions import ClientError
from config import *

class ResourceGroupTag:
    def __init__(self):
        self.logger=logging.getLogger("ResourceGroupTag")
    
    
    def fetch_all_resources_for_processing(self):
        response = resourcegroupclient.get_resources(
            ResourceTypeFilters=['ec2:instance'],
            TagFilters=[{'Key': TAG_ENABLED_KEY, 'Values': [TAG_ENABLED_VALUES['Available']]}]
        )
        return response.get('ResourceTagMappingList', [])

    def getDetailByArn(resourceArn):
        splitArn = resourceArn.split(':')
        resourceDetails={}
        resourceDetails['service'] = splitArn[2]
        resourceDetails['region'] = splitArn[3]
        resourceDetails['accountId'] = splitArn[4]
        resourceDetails['resourceId'] = ':'.join(splitArn[5:])
        return resourceDetails

class EC2Processor:
    def __init__(self):
        self.logger=logging.getLogger("EC2Processor")
        
    def get_instance_id(self, resource):
        resource_arn = resource['ResourceARN']
        return resource_arn.split('/')[-1]
        
    def validate_instance_status(self, instance_id):
        try:
            response = ec2_client.describe_instances(InstanceIds=[instance_id])
            print(response)
            instance = response['Reservations'][0]['Instances'][0]
            InstanceState=instance['State']['Name']
            if InstanceState == 'running':
                return True
            self.logger.debug(f"Error checking instance status: Instance is {InstanceState}")
            print(instance_id, InstanceState)
        except ClientError as e:
            self.logger.error(f"Error checking instance status: {e}")
        return False
        
    def get_instance_details(self, instance_id):
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        if 'PlatformDetails' in instance:
            platform = instance.get('PlatformDetails', 'Linux')
            instance_type = instance['InstanceType']
        elif 'Platform' in instance:
            platform = instance.get('Platform', 'Windows')
            instance_type = instance['InstanceType']
        return platform, instance_type
        
class SSMProcessor:
    def __init__(self):
        self.logger=logging.getLogger("SSMProcessor")
    
    def execute_ssm_command(self, instance_id, document_name):
        try:
            Id = [instance_id]
            response = ssm_client.send_command(
                InstanceIds=Id,
                DocumentName=document_name,
                TimeoutSeconds=60
            )
            CommandInfo = response['Command']['CommandId']
            self.logger.info(response)
            return CommandInfo
        
        except ssm_client.exceptions.InvalidInstanceId as e:
            print(f"InvalidInstanceId error: {e}")
            return 'NoCommandID'
            
        except ClientError as e:
            print(f"Unexpected error: {e}")
            return 'Boto3ClientError'
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            return "UnExpectedError"
            
        
    def get_command_status(self, instance_id, command_id):
        response = ssm_client.list_command_invocations(CommandId=command_id)
        if response['CommandInvocations']:
            return response['CommandInvocations'][0]['Status']
        return None
    
    def get_document_name(self, instance_type, platform):
        if 'Linux' in platform:
            Type=instance_type.split('.')
            if 'a' in Type[0]:
                OS='AMD'
            elif 'g' in Type[0]:
                OS='ARM'
            else:
                OS='Intel'
            return f'OpenTelemetryInstallation-Linux-{OS}'
        elif platform=='Windows':
            return 'OpenTelemetryInstallation-Windows'

    def process_otel_service(self, instance_id):
        platform, instance_type = EC2Processor.get_instance_details(self,instance_id)
        document_name = SSMProcessor.get_document_name(self,instance_type, platform)
        command_id = SSMProcessor.execute_ssm_command(self,instance_id, document_name)
        time.sleep(10)
        return command_id
    
    
class Tagger:
    def __init__(self):
        self.logger=logging.getLogger("Tagger")
    
    def markResourceAsSuccessful(resource):
        resourceARN = resource['ResourceARN']
        resourcegroupclient.tag_resources(
            ResourceARNList=[resourceARN],
            Tags={TAG_ENABLED_KEY: TAG_ENABLED_VALUES['Success']}
        )
        print(f"Marked as Successful {resource}")
        
    def markResourceAsFailed(resource):
        resourceARN = resource['ResourceARN']
        resourcegroupclient.tag_resources(
            ResourceARNList=[resourceARN],
            Tags={TAG_ENABLED_KEY: TAG_ENABLED_VALUES['Failed']}
        )
        print(f"Marked as Failed {resource}")

    def markResourceAsInvalid(resource):
        resourceARN = resource['ResourceARN']
        resourcegroupclient.tag_resources(
            ResourceARNList=[resourceARN],
            Tags={TAG_ENABLED_KEY: TAG_ENABLED_VALUES['Invalid']}
        )
        print(f"Marked as Invalid {resource}")
    
    def getDictionaryFromList(lstTags):
        return {tag['Key']: tag['Value'] for tag in lstTags}