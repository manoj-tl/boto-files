import boto3
import csv
from datetime import datetime
from botocore.exceptions import ClientError

def get_regions():
    ec2 = boto3.client('ec2')
    return [region['RegionName'] for region in ec2.describe_regions()['Regions']]

def discover_resources(region):
    client = boto3.client('resourcegroupstaggingapi', region_name=region)
    resources = []
    paginator = client.get_paginator('get_resources')
    
    try:
        for page in paginator.paginate():
            resources.extend(page['ResourceTagMappingList'])
        return resources
    except ClientError as e:
        print(f"Error in region {region}: {str(e)}")
        return []

def tag_resource(resource_arn, region):
    client = boto3.client('resourcegroupstaggingapi', region_name=region)
    try:
        response = client.tag_resources(
            ResourceARNList=[resource_arn],
            Tags={'CostCenter': '12345'}
        )
        return response['FailedResourcesMap']
    except ClientError as e:
        return {resource_arn: str(e)}

def main():
    regions = get_regions()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Files for logging
    resource_file = f'discovered_resources_{timestamp}.csv'
    results_file = f'tagging_results_{timestamp}.csv'
    
    # Discover and list resources
    print("Discovering resources...")
    with open(resource_file, 'w', newline='') as f_resources, open(results_file, 'w', newline='') as f_results:
        resource_writer = csv.writer(f_resources)
        resource_writer.writerow(['Region', 'ResourceARN', 'Current Tags'])
        
        results_writer = csv.writer(f_results)
        results_writer.writerow(['Region', 'ResourceARN', 'Status', 'Error'])
        
        for region in regions:
            print(f"\nScanning region: {region}")
            resources = discover_resources(region)
            
            for resource in resources:
                resource_arn = resource['ResourceARN']
                print(f"Found resource: {resource_arn}")
                
                # Write to discovered resources file
                resource_writer.writerow([
                    region,
                    resource_arn,
                    str(resource.get('Tags', {}))
                ])
                
               
                # # Immediately tag the resource
                # failed = tag_resource(resource_arn, region)
                # if failed:
                #     status = 'Failed'
                #     error = failed.get(resource_arn, 'Unknown error')
                #     print(f"✗ Failed to tag: {resource_arn} - {error}")
                # else:
                #     status = 'Success'
                #     error = ''
                #     print(f"✓ Successfully tagged: {resource_arn}")
                
                # # Write results
                # results_writer.writerow([region, resource_arn, status, error])
           
    
    print(f"\nComplete! Resources discovered are saved in {resource_file}")

if __name__ == "__main__":
    main()