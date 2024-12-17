import boto3
import csv
import yaml
from datetime import datetime
from botocore.exceptions import ClientError

# North America Regions
TARGET_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']

def read_accounts():
    try:
        with open('accounts.yaml', 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"Error reading YAML file: {str(e)}")
        return {}

def assume_role(account_id):
    role_arn = f'arn:aws:iam::{account_id}:role/Devops-Admin-Role'
    sts_client = boto3.client('sts')
    try:
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ResourceDiscoverySession'
        )
        return boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken']
        )
    except Exception as e:
        print(f"Error assuming role for account {account_id}: {str(e)}")
        return None

def discover_resources(region, session=None):
    if session:
        client = session.client('resourcegroupstaggingapi', region_name=region)
    else:
        client = boto3.client('resourcegroupstaggingapi', region_name=region)
    
    resources = []
    paginator = client.get_paginator('get_resources')
    
    try:
        for page in paginator.paginate():
            # Filter resources that don't have CostString tag
            for resource in page['ResourceTagMappingList']:
                tags = resource.get('Tags', {})
                if 'CostString' not in tags:
                    resources.append(resource)
        return resources
    except ClientError as e:
        print(f"Error in region {region}: {str(e)}")
        return []

def tag_resources_batch(resource_arns, region, session=None):
    if session:
        client = session.client('resourcegroupstaggingapi', region_name=region)
    else:
        client = boto3.client('resourcegroupstaggingapi', region_name=region)
    
    try:
        response = client.tag_resources(
            ResourceARNList=resource_arns,
            Tags={'CostString': 'your-cost-center-here'}
        )
        return response['FailedResourcesMap']
    except ClientError as e:
        return {arn: str(e) for arn in resource_arns}

def main():
    accounts = read_accounts()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for account_name, account_id in accounts.items():
        print(f"\nProcessing account: {account_name} ({account_id})")
        
        session = assume_role(account_id)
        if not session:
            print(f"Skipping account {account_name} due to role assumption failure")
            continue
        
        resource_file = f'discovered_resources_{account_name}_{timestamp}.csv'
        results_file = f'tagging_results_{account_name}_{timestamp}.csv'
        
        print(f"Discovering resources without CostString tag for {account_name}...")
        with open(resource_file, 'w', newline='') as f_resources, \
             open(results_file, 'w', newline='') as f_results:
            
            resource_writer = csv.writer(f_resources)
            results_writer = csv.writer(f_results)
            
            resource_writer.writerow(['Region', 'ResourceARN', 'Current Tags'])
            results_writer.writerow(['Region', 'ResourceARN', 'Status', 'Error'])
            
            for region in TARGET_REGIONS:
                print(f"\nScanning region: {region}")
                resources = discover_resources(region, session)
                if not resources:
                    print(f"No resources without CostString tag found in {region}")
                    continue

                batch = []
                
                for resource in resources:
                    resource_arn = resource['ResourceARN']
                    print(f"Found resource without CostString tag: {resource_arn}")
                    
                    # Write to discovered resources file
                    resource_writer.writerow([
                        region,
                        resource_arn,
                        str(resource.get('Tags', {}))
                    ])
                    
                    batch.append(resource_arn)
                    
                    # Process batch when it reaches size 20 or last resource
                    if len(batch) == 20 or resource == resources[-1]:
                        failed_resources = tag_resources_batch(batch, region, session)
                        
                        # Write results for the batch
                        for arn in batch:
                            if arn in failed_resources:
                                status = 'Failed'
                                error = failed_resources.get(arn, 'Unknown error')
                                print(f"✗ Failed to tag: {arn} - {error}")
                            else:
                                status = 'Success'
                                error = ''
                                print(f"✓ Successfully tagged: {arn}")
                            
                            results_writer.writerow([region, arn, status, error])
                        
                        batch = [] 
        
        print(f"Complete! Results for {account_name} saved in:")
        print(f"- Resources: {resource_file}")
        print(f"- Tagging Results: {results_file}")

if __name__ == "__main__":
    main()