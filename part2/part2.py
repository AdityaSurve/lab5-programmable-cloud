#!/usr/bin/env python3

import argparse
import time

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
compute = googleapiclient.discovery.build(
    'compute', 'v1', credentials=credentials)

ZONE = "us-west1-b"
INSTANCE_NAME = "flask-vm"


def wait_for_zone_operation(compute, project, zone, op_name):
    while True:
        op = compute.zoneOperations().get(
            project=project, zone=zone, operation=op_name
        ).execute()
        if op["status"] == "DONE":
            if "error" in op:
                raise RuntimeError(op["error"])
            return op
        time.sleep(2)


def create_snapshot(compute, project, zone, instance_name):
    instance = compute.instances().get(
        project=project, zone=zone, instance=instance_name
    ).execute()

    disk_selflink = instance["disks"][0]["source"]

    snapshot_body = {
        "name": f"base-snapshot-{instance_name}"
    }

    op = compute.disks().createSnapshot(
        project=project, zone=zone, disk=instance_name, body=snapshot_body
    ).execute()

    wait_for_zone_operation(compute, project, zone, op["name"])


def create_vm_from_snapshot(compute, project, zone, name, snapshot_name):
    config = {
        "name": name,
        "machineType": f"zones/{zone}/machineTypes/e2-medium",
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceSnapshot": f"projects/{project}/global/snapshots/{snapshot_name}"
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
    create_snapshot(compute, project, ZONE, INSTANCE_NAME)

    for i in range(3):
        instance_name = f"flask-vm-clone-{i+1}"
        print(f"Creating instance: {instance_name}")
        create_vm_from_snapshot(compute, project, ZONE,
                                instance_name, f"base-snapshot-{INSTANCE_NAME}")


if __name__ == "__main__":
    main()
