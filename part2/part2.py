#!/usr/bin/env python3

import time
from pprint import pprint
import googleapiclient.discovery
import google.auth
from googleapiclient.errors import HttpError

credentials, PROJECT = google.auth.default()
ZONE = "us-west1-b"
SOURCE_INSTANCE = "lab5-flask-vm"
SNAPSHOT_NAME = f"base-snapshot-{SOURCE_INSTANCE}"
CLONE_PREFIX = "clone-vm"
MACHINE_TYPE = "f1-micro"

compute = googleapiclient.discovery.build(
    'compute', 'v1', credentials=credentials)


def wait_for_zone_op(operation):
    name = operation['name']
    print(f"Waiting for zone operation {name}...")
    while True:
        result = compute.zoneOperations().get(
            project=PROJECT, zone=ZONE, operation=name).execute()
        if result.get('status') == 'DONE':
            if 'error' in result:
                raise Exception(result['error'])
            print("Operation finished.")
            return
        time.sleep(1)


def create_snapshot():
    try:
        instance = compute.instances().get(project=PROJECT, zone=ZONE,
                                           instance=SOURCE_INSTANCE).execute()
        boot_disk = instance['disks'][0]['source'].split('/')[-1]

        print(f"Creating snapshot {SNAPSHOT_NAME} from disk {boot_disk}...")
        op = compute.disks().createSnapshot(
            project=PROJECT,
            zone=ZONE,
            disk=boot_disk,
            body={"name": SNAPSHOT_NAME}
        ).execute()
        wait_for_zone_op(op)
        print("Snapshot created.")
    except HttpError as e:
        if int(getattr(e.resp, "status", 0)) == 409:
            print("Snapshot already exists, skipping creation.")
        else:
            raise


def create_instance_from_snapshot(name):
    config = {
        "name": name,
        "machineType": f"projects/{PROJECT}/zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
        "disks": [{
            "boot": True,
            "autoDelete": True,
            "initializeParams": {
                "sourceSnapshot": f"projects/{PROJECT}/global/snapshots/{SNAPSHOT_NAME}"
            }
        }],
        "networkInterfaces": [{
            "network": f"projects/{PROJECT}/global/networks/default",
            "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
        }],
    }
    start = time.time()
    op = compute.instances().insert(project=PROJECT, zone=ZONE, body=config).execute()
    wait_for_zone_op(op)
    end = time.time()
    print(f"Instance {name} created in {end - start:.2f} seconds.")
    return end - start


def main():
    create_snapshot()
    timings = []
    for i in range(1, 4):
        vm_name = f"{CLONE_PREFIX}-{i}"
        duration = create_instance_from_snapshot(vm_name)
        timings.append((vm_name, duration))

    with open("TIMING.md", "w") as f:
        f.write("# VM Creation Timings\n\n")
        for vm, t in timings:
            f.write(f"{vm}: {t:.2f} seconds\n")
    print("\n🎉 VM creation timings saved to TIMING.md")


if __name__ == "__main__":
    main()
