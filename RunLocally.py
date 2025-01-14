import json
import logging
import boto3
import datetime
from datetime import timezone
from botocore.exceptions import ClientError

logging.basicConfig(
    level = logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("OpenTelemetryService")

TAG_ENABLED_KEY='OpenTelemetry:Status'
TAG_ENABLED_VALUES={
    "Available":"1",    # Pick for processing
    "Success":"2",      # Successful
    "Failed":"3"}       # Failed

resourcegroupclient = boto3.client('resourcegroupstaggingapi')
ssm_client = boto3.client('ssm')
ec2_resource = boto3.resource('ec2')

def lambda_handler(event, context):    
    resource_list = fetchAllResourcesForProcessing()
    if len(resource_list)>0:
        print(resource_list)
        logger.info("Found resources to process")
        processResources(resource_list)    
    

def fetchAllResourcesForProcessing():       
    response = resourcegroupclient.get_resources(
    ResourceTypeFilters=['ec2:instance'],
    TagFilters=[
        {
        'Key':TAG_ENABLED_KEY,
        'Values':[            
            TAG_ENABLED_VALUES['Available']
            ]
        }])    
    resourceList = response['ResourceTagMappingList']
    return resourceList


def processResources(lstResources):
    for resource in lstResources:
        try:            
            logger.info("Processing resource..")
            logger.info(resource)
            # Get Instance Id
            resourceArn = resource['ResourceARN']
            instanceId = getDetailByArn(resourceArn)['resourceId'].replace("instance/","")

            # Get Tags
            resourceTags = getDictionaryFromList(resource['Tags'])

            # Perform validation
            if(validateInstanceStatus(instanceId)):                
                processOTelService(instanceId,resourceTags)
                markResourceAsSuccessful(resource)
                print("Processed OpenTelemetry Service successfully..")
                logger.info("Processed OpenTelemetry Service successfully..")
            else:
                logger.info("Instance is not running state..")       
        except Exception as ex:
            logger.info("Processing failed..")
            markResourceAsFailed(resource)
            logger.error(ex)     

def processOTelService(instanceId,resourceTags):
    try:
        if(validateTagsForOTel(resourceTags)):
            print("Running SSM Command")
            InstanceType,Platform=getinstancetypeandplatform(instanceId)
            Type=InstanceType.split('.')
            if 'a' in Type[0]:
                OS='amd'
                executeSSMCommand(instanceId)
            
        else:
            raise Exception("Missing mandatory tags")    
        
    except Exception as ex:
        raise ex



def executeSSMCommand(instanceId,DocName):
    # TODO
    # Manage document version externally
    print(instanceId)
    response = ssm_client.send_command(
            InstanceIds=[instanceId],
            DocumentName=DocName,

            TimeoutSeconds=30)
    print(response)
    logger.info(response)
    


def getDetailByArn(resourceArn):
    splitArn = resourceArn.split(':')
    resourceDetails={}
    resourceDetails['service'] = splitArn[2]
    resourceDetails['region'] = splitArn[3]
    resourceDetails['accountId'] = splitArn[4]
    resourceDetails['resourceId'] = ':'.join(splitArn[5:])
    return resourceDetails

def validateInstanceStatus(instanceId):    
    instance_running=False
    try:
        instance = ec2_resource.Instance(instanceId)    
        instance_launchtime = instance.launch_time
        now = datetime.datetime.now(timezone.utc)
        timeToCheck = now - datetime.timedelta(minutes=10)
        
        if instance.state['Name'] == 'running' :
            instance_running = True
    except Exception as ex:
        logger.error(ex)
    print(instance_running)
    return instance_running

def validateTagsForOTel(resourceTags):
    isValid=resourceTags.keys()>={
        "OpenTelemetry:Status"
        }
    return isValid

def getDictionaryFromList(lstTags):
    tagDict={}
    for tag in lstTags:
        tagDict[tag['Key']]=tag['Value']
    return tagDict

def markResourceAsSuccessful(resource):        
    resourceARN=resource['ResourceARN']
    resourcegroupclient.tag_resources(
        ResourceARNList=[
            resourceARN                
            ],
        Tags={
            TAG_ENABLED_KEY:TAG_ENABLED_VALUES['Success']
            })
    print("Tag marked as Successful...")
def markResourceAsFailed(resource):    
    resourceARN=resource['ResourceARN']
    resourcegroupclient.tag_resources(
        ResourceARNList=[
            resourceARN                
            ],
        Tags={
            TAG_ENABLED_KEY:TAG_ENABLED_VALUES['Failed']
            })
    print("Tag marked as Failed...")
    # TODO
    # Raise exception to SNS in case of failure

def getinstancetypeandplatform(id):
    try:
        response=ec2_resource.describe_instances(InstanceIds=[id])
        if 'Reservations' in response:
            instance = response['Reservations'][0]['Instances'][0]
        return instance['InstanceType'],instance['Platform']
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
            print("The instance ID does not exist.")
            logger.debug("The instance ID does not exist.")
            return ''
        else:
            print("An error occurred:", e)
            logger.error("The instance ID does not exist.")
            return ''

if __name__ == '__main__':
    lambda_handler({},{})    