import boto3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# AWS Clients
resourcegroupclient = boto3.client('resourcegroupstaggingapi')
ssm_client = boto3.client('ssm')
ec2_client = boto3.client('ec2')
ec2_resource = boto3.resource('ec2')

# Constants for tagging
TAG_ENABLED_KEY = 'LSQ:OpenTelemetry:Status'
TAG_ENABLED_VALUES = {
    "Available": "1",
    "Success": "2",
    "Failed": "3",
    "Invalid": "4"
}
