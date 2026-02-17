#!/usr/bin/env python3

import argparse
import os
import googleapiclient.discovery
import google.auth
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    'service-credentials.json')
project = os.getenv('GOOGLE_CLOUD_PROJECT') or 'FILL IN YOUR PROJECT'
service = googleapiclient.discovery.build(
    'compute', 'v1', credentials=credentials)

ZONE = "us-west1-b"


def create_vm_from_service_account(compute, project, zone, name):
    config = {
        "name": name,
        "machineType": f"zones/{zone}/machineTypes/e2-medium",
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
                },
            }
        ],
        "networkInterfaces": [
            {
                "network": "global/networks/default",
                "accessConfigs": [
                    {"name": "External NAT", "type": "ONE_TO_ONE_NAT"}
                ],
            }
        ],
    }

    op = compute.instances().insert(project=project, zone=zone, body=config).execute()
    wait_for_zone_operation(compute, project, zone, op["name"])


def main():
    instance_name = "vm1-created-by-service-account"
    print(f"Creating VM {instance_name}...")
    create_vm_from_service_account(service, project, ZONE, instance_name)


if __name__ == "__main__":
    main()
