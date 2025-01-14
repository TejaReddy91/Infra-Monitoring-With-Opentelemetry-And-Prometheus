from OpenTelemetry import OTelService

def lambda_handler(event, context):
    service = OTelService()
    service.run()