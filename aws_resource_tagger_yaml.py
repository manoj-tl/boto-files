import boto3
import csv
import hcl2
from datetime import datetime
from botocore.exceptions import ClientError


TARGET_REGIONS = ['us-east-1', 'us-west-2', 'eu-west-1']

def read_accounts():
    try:
        with open('locals.tf', 'r') as file:
            parsed_hcl = hcl2.load(file)
            return parsed_hcl['locals'][0]['account_ids']
    except Exception as e:
        print(f"Error reading locals.tf file: {str(e)}")
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
            resources.extend(page['ResourceTagMappingList'])
        return resources
    except ClientError as e:
        print(f"Error in region {region}: {str(e)}")
        return []

def tag_resource(resource_arn, region, session=None):
    if session:
        client = session.client('resourcegroupstaggingapi', region_name=region)
    else:
        client = boto3.client('resourcegroupstaggingapi', region_name=region)
    
    try:
        response = client.tag_resources(
            ResourceARNList=[resource_arn],
            Tags={'CostCenter': 'your-cost-center-here'}
        )
        return response['FailedResourcesMap']
    except ClientError as e:
        return {resource_arn: str(e)}

def main():
    accounts = read_accounts()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for account_name, account_id in accounts.items():
        print(f"\nProcessing account: {account_name} ({account_id})")
        
        # Assume role for the account
        session = assume_role(account_id)
        if not session:
            print(f"Skipping account {account_name} due to role assumption failure")
            continue
        
        # Files for logging (per account)
        resource_file = f'discovered_resources_{account_name}_{timestamp}.csv'
        results_file = f'tagging_results_{account_name}_{timestamp}.csv'
        
        # Discover and list resources
        print(f"Discovering resources for {account_name}...")
        with open(resource_file, 'w', newline='') as f_resources, \
             open(results_file, 'w', newline='') as f_results:
            
            resource_writer = csv.writer(f_resources)
            results_writer = csv.writer(f_results)
            
            resource_writer.writerow(['Region', 'ResourceARN', 'Current Tags'])
            results_writer.writerow(['Region', 'ResourceARN', 'Status', 'Error'])
            
            for region in TARGET_REGIONS:
                print(f"\nScanning region: {region}")
                resources = discover_resources(region, session)
                
                for resource in resources:
                    resource_arn = resource['ResourceARN']
                    print(f"Found resource: {resource_arn}")
                    
                    # Write to discovered resources file
                    resource_writer.writerow([
                        region,
                        resource_arn,
                        str(resource.get('Tags', {}))
                    ])
                    
                    # Tag the resource
                    tag_response = tag_resource(resource_arn, region, session)
                    if tag_response:
                        status = 'Failed'
                        error = tag_response.get(resource_arn, 'Unknown error')
                        print(f"✗ Failed to tag: {resource_arn} - {error}")
                    else:
                        status = 'Success'
                        error = ''
                        print(f"✓ Successfully tagged: {resource_arn}")
                    
                    # Write results
                    results_writer.writerow([region, resource_arn, status, error])
        
        print(f"Complete! Results for {account_name} saved in:")
        print(f"- Resources: {resource_file}")
        print(f"- Tagging Results: {results_file}")

if __name__ == "__main__":
    main()