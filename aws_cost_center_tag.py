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

def discover_resources_with_costcenter(region, session=None):
    """Discover resources that have CostCenter tag"""
    if session:
        client = session.client('resourcegroupstaggingapi', region_name=region)
    else:
        client = boto3.client('resourcegroupstaggingapi', region_name=region)
    
    resources = []
    paginator = client.get_paginator('get_resources')
    
    try:
        for page in paginator.paginate():
            for resource in page['ResourceTagMappingList']:
                tags = resource.get('Tags', {})
                if 'CostCenter' in tags:
                    resources.append({
                        'ResourceARN': resource['ResourceARN'],
                        'CostCenterValue': tags['CostCenter']
                    })
        return resources
    except ClientError as e:
        print(f"Error in region {region}: {str(e)}")
        return []

def delete_tags_batch(resource_arns, region, session=None):
    """Delete CostCenter tag in batches"""
    if session:
        client = session.client('resourcegroupstaggingapi', region_name=region)
    else:
        client = boto3.client('resourcegroupstaggingapi', region_name=region)
    
    try:
        response = client.untag_resources(
            ResourceARNList=resource_arns,
            TagKeys=['CostCenter']
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
        
        results_file = f'tag_deletion_{account_name}_{timestamp}.csv'
        
        print(f"Discovering resources with CostCenter tag for {account_name}...")
        with open(results_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Region', 'ResourceARN', 'Old CostCenter Value', 'Status', 'Error'])
            
            for region in TARGET_REGIONS:
                print(f"\nScanning region: {region}")
                resources = discover_resources_with_costcenter(region, session)
                
                if not resources:
                    print(f"No resources with CostCenter tag found in {region}")
                    continue

                print(f"Found {len(resources)} resources with CostCenter tag in {region}")
                
                # Process in batches of 20
                batch_size = 20
                for i in range(0, len(resources), batch_size):
                    batch = resources[i:i + batch_size]
                    batch_arns = [r['ResourceARN'] for r in batch]
                    
                    failed_resources = delete_tags_batch(batch_arns, region, session)
                    
                    # Write results for the batch
                    for resource in batch:
                        arn = resource['ResourceARN']
                        if arn in failed_resources:
                            status = 'Failed'
                            error = failed_resources.get(arn, 'Unknown error')
                            print(f"✗ Failed to delete CostCenter tag: {arn} - {error}")
                        else:
                            status = 'Success'
                            error = ''
                            print(f"✓ Successfully deleted CostCenter tag: {arn}")
                        
                        writer.writerow([
                            region,
                            arn,
                            resource['CostCenterValue'],
                            status,
                            error
                        ])
        
        print(f"\nComplete! Results for {account_name} saved in: {results_file}")

if __name__ == "__main__":
    main()