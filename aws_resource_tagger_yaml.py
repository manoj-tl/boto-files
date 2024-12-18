import boto3
import csv
import yaml
from datetime import datetime
from botocore.exceptions import ClientError

'''
Script will update "CostStrig" tag for the resources that doesn't have CostString atached. 
It loops thru multiple accounts by checking the accounts.yaml file in path of the script
Example accounts.yaml:
'''

TARGET_REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']

def read_accounts():
    try:
        with open('accounts.yaml', 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"Error reading YAML file: {str(e)}")
        return {}

def assume_role(account_id):
    role_arn = f'arn:aws:iam::{account_id}:role/{account_id}-Devops-Admin-Role'
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
        # Get resources including those with no tags
        for page in paginator.paginate(
            ResourcesPerPage=100,
            IncludeComplianceDetails=True,
            ResourceTypeFilters=[]
        ):
            for resource in page['ResourceTagMappingList']:
                # Check if resource has any tags
                if not resource.get('Tags'):
                    # resources.append(resource)
                    print(f"Found completely untagged resource: {resource['ResourceARN']}")
                    continue
                
                # Check for CostString tag
                has_coststring = False
                for tag in resource.get('Tags', []):
                    if tag.get('Key', '').lower() == 'coststring':
                        has_coststring = True
                        resources.append(resource)
                        print(f"Resource with Old CostString tag: {resource['ResourceARN']}")
                        break
                
                if not has_coststring:
                    resources.append(resource)
                    print(f"No CostString tag found for: {resource['ResourceARN']}")
        
        print(f"Total resources found in {region}: {len(resources)}")
        print(f"- Untagged resources: {sum(1 for r in resources if not r.get('Tags'))}")
        print(f"- Resources without CostString: {sum(1 for r in resources if r.get('Tags'))}")
        
        return resources
    except ClientError as e:
        print(f"Error in region {region}: {str(e)}")
        return []


def tag_resources(resource_arns, region, session=None):
    if session:
        client = session.client('resourcegroupstaggingapi', region_name=region)
    else:
        client = boto3.client('resourcegroupstaggingapi', region_name=region)
    
    try:
        response = client.tag_resources(
            ResourceARNList=resource_arns,
            Tags={'CostString': '1100.us.624.402026.66004000'}
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
        
        resource_file = f'discovered_resources_{account_id}_{timestamp}.csv'
        results_file = f'tagging_results_{account_id}_{timestamp}.csv'
        
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
                    
                    # Updates in batch of 20 resources to run faster
                    if len(batch) == 20 or resource == resources[-1]:
                        tagging_resources = tag_resources(batch, region, session)
                        
                        # Write results for the batch
                        for arn in batch:
                            if arn in tagging_resources:
                                status = 'Failed'
                                error = tagging_resources.get(arn, 'Unknown error')
                                print(f"Failed to tag: {arn} - {error}")
                            else:
                                status = 'Success'
                                error = ''
                                print(f"Successfully tagged: {arn}")
                            
                            results_writer.writerow([region, arn, status, error])
                        
                        batch = [] 
        
        print(f"Complete! Results for {account_name} saved in:")
        print(f"- Resources: {resource_file}")
        print(f"- Tagging Results: {results_file}")

if __name__ == "__main__":
    main()