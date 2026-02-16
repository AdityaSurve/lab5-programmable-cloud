#!/usr/bin/env python3

import argparse
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth
from googleapiclient.errors import HttpError

credentials, project = google.auth.default()
service = googleapiclient.discovery.build(
    'compute', 'v1', credentials=credentials)

ZONE = "us-west1-b"
FIREWALL_NAME = "allow-5000"
NETWORK_TAG = "allow-5000"
IMAGE_FAMILY = "ubuntu-2204-lts"
IMAGE_PROJECT = "ubuntu-os-cloud"

STARTUP_SCRIPT = """#!/bin/bash
set -euxo pipefail

mkdir -p /srv/flask
cd /srv/flask

apt-get update
apt-get install -y python3 python3-pip git

git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial
cd flask-tutorial

python3 setup.py install
pip3 install -e .

export FLASK_APP=flaskr
flask init-db

nohup flask run -h 0.0.0.0 -p 5000 &
"""

def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result['items'] if 'items' in result else []


def wait_for_zone_op(compute, project, zone, op_name):
    while True:
        op = compute.zoneOperations().get(
            project=project, zone=zone, operation=op_name
        ).execute()
        if op.get("status") == "DONE":
            if "error" in op:
                raise RuntimeError(op["error"])
            return op
        time.sleep(2)


def wait_for_global_op(compute, project, op_name):
    while True:
        op = compute.globalOperations().get(
            project=project, operation=op_name
        ).execute()
        if op.get("status") == "DONE":
            if "error" in op:
                raise RuntimeError(op["error"])
            return op
        time.sleep(2)


def get_ubuntu_image_selflink(compute):
    img = compute.images().getFromFamily(
        project=IMAGE_PROJECT,
        family=IMAGE_FAMILY
    ).execute()
    return img["selfLink"]


def instance_exists(compute, project, zone, name):
    try:
        compute.instances().get(project=project, zone=zone, instance=name).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise


def create_instance(compute, project, zone, name, machine_type):
    source_image = get_ubuntu_image_selflink(compute)
    config = {
        "name": name,
        "machineType": f"zones/{zone}/machineTypes/{machine_type}",
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": source_image
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
        "metadata": {
            "items": [
                {"key": "startup-script", "value": STARTUP_SCRIPT}
            ]
        },
    }
    op = compute.instances().insert(project=project, zone=zone, body=config).execute()
    wait_for_zone_op(compute, project, zone, op["name"])


def firewall_rule_exists_by_list(compute, project, name):
    req = compute.firewalls().list(project=project)
    while req is not None:
        resp = req.execute()
        for fw in resp.get("items", []):
            if fw.get("name") == name:
                return True
        req = compute.firewalls().list_next(previous_request=req, previous_response=resp)
    return False


def ensure_firewall_allow_5000(compute, project):
    if firewall_rule_exists_by_list(compute, project, FIREWALL_NAME):
        return
    body = {
        "name": FIREWALL_NAME,
        "network": "global/networks/default",
        "direction": "INGRESS",
        "priority": 1000,
        "sourceRanges": ["0.0.0.0/0"],
        "allowed": [
            {"IPProtocol": "tcp", "ports": ["5000"]}
        ],
        "targetTags": [NETWORK_TAG],
    }
    op = compute.firewalls().insert(project=project, body=body).execute()
    wait_for_global_op(compute, project, op["name"])


def add_network_tag_via_setTags(compute, project, zone, instance_name, tag):
    inst = compute.instances().get(project=project, zone=zone,
                                   instance=instance_name).execute()
    tags = inst.get("tags", {})
    fingerprint = tags.get("fingerprint")
    items = tags.get("items", [])
    if tag in items:
        return
    new_items = items + [tag]
    body = {
        "items": new_items,
        "fingerprint": fingerprint
    }
    op = compute.instances().setTags(
        project=project, zone=zone, instance=instance_name, body=body
    ).execute()
    wait_for_zone_op(compute, project, zone, op["name"])


def get_external_ip(compute, project, zone, instance_name):
    inst = compute.instances().get(project=project, zone=zone,
                                   instance=instance_name).execute()
    return inst["networkInterfaces"][0]["accessConfigs"][0]["natIP"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="flask-vm", help="Instance name")
    parser.add_argument("--machine_type", default="f1-micro",
                        help="Machine type (default f1-micro)")
    args = parser.parse_args()
    print("Your running instances are:")
    for instance in list_instances(service, project, 'us-west1-b'):
        print(instance['name'])
    if not instance_exists(service, project, ZONE, args.name):
        create_instance(service, project, ZONE, args.name, args.machine_type)
    ensure_firewall_allow_5000(service, project)
    add_network_tag_via_setTags(service, project, ZONE, args.name, NETWORK_TAG)
    ip = get_external_ip(service, project, ZONE, args.name)
    print(f"http://{ip}:5000")


if __name__ == "__main__":
    main()
