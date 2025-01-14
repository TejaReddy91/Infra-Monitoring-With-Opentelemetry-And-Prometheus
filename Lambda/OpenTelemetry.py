import logging
from AWSUtility import *

class OTelService:
    def __init__(self):
        self.logger = logging.getLogger("OTelService")
        
    def process_resource(self,resource):
        try:
            self.logger.info(f"Processing resource: {resource}")
            instance_id = EC2Processor.get_instance_id(self,resource)
            resource_tags = Tagger.getDictionaryFromList(resource['Tags'])

            if EC2Processor.validate_instance_status(self,instance_id):
                command_id = SSMProcessor.process_otel_service(self,instance_id)
                if command_id == 'NoCommandID':
                    Tagger.markResourceAsInvalid(resource)
                else:
                    status = SSMProcessor.get_command_status(self,instance_id, command_id)
                    if status == 'Success':
                        Tagger.markResourceAsSuccessful(resource)
                    elif status in ['Pending','InProgress']:
                        self.logger.info(f"Command in {instance_id} is Still Pending")
                    else:
                        Tagger.markResourceAsFailed(resource)
            else:
                self.logger.info(f"Instance {instance_id} is not in running state.")
        except Exception as e:
            self.logger.error(f"Failed to process resource: {resource}. Error: {e}")
            Tagger.markResourceAsFailed(resource)

    def run(self):
        resource_list = ResourceGroupTag.fetch_all_resources_for_processing(self)
        self.logger.info(f"Found {len(resource_list)} resources to process.")
        if resource_list:
            for resource in resource_list:
                self.process_resource(resource)