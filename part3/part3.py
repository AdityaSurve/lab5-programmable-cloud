import os
import time
from googleapiclient import discovery
from google.oauth2 import service_account

PROJECT = "lab5-487723"
ZONE = "us-west1-b"
VM1_NAME = "vm1-launcher"
MACHINE_TYPE = "e2-medium"
IMAGE_PROJECT = "debian-cloud"
IMAGE_FAMILY = "debian-11"

credentials = service_account.Credentials.from_service_account_file(
    "service-credentials.json"
)

compute = discovery.build("compute", "v1", credentials=credentials)

vm2_startup_script = """#!/bin/bash
sudo apt-get update
sudo apt-get install -y python3-pip git
pip3 install flask
cat <<EOF > /home/flask_app.py
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello from VM-2 running Flask!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
EOF
nohup python3 /home/flask_app.py &
"""

vm1_launch_vm2_code = f"""#!/usr/bin/env python3
import time
from googleapiclient import discovery
from google.oauth2 import service_account

PROJECT = "{PROJECT}"
ZONE = "{ZONE}"
VM2_NAME = "vm2-flask"
MACHINE_TYPE = "e2-micro"
IMAGE_PROJECT = "{IMAGE_PROJECT}"
IMAGE_FAMILY = "{IMAGE_FAMILY}"

credentials = service_account.Credentials.from_service_account_file(
    "/srv/service-credentials.json"
)
compute = discovery.build("compute", "v1", credentials=credentials)

startup_script = \"\"\"{vm2_startup_script}\"\"\"

config = {{
    "name": VM2_NAME,
    "machineType": f"zones/{{ZONE}}/machineTypes/{{MACHINE_TYPE}}",
    "disks": [
        {{
            "boot": True,
            "autoDelete": True,
            "initializeParams": {{
                "sourceImage": compute.images().getFromFamily(
                    project=IMAGE_PROJECT, family=IMAGE_FAMILY).execute()["selfLink"]
            }}
        }}
    ],
    "networkInterfaces": [{{
        "network": "global/networks/default",
        "accessConfigs": [{{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}}]
    }}],
    "metadata": {{
        "items": [{{
            "key": "startup-script",
            "value": startup_script
        }}]
    }}
}}

print("Creating VM-2 with Flask...")
operation = compute.instances().insert(project=PROJECT, zone=ZONE, body=config).execute()

while True:
    result = compute.zoneOperations().get(
        project=PROJECT,
        zone=ZONE,
        operation=operation["name"]).execute()
    if result["status"] == "DONE":
        print("VM-2 created successfully!")
        break
    time.sleep(5)
"""

vm1_startup_script = """#!/bin/bash
mkdir -p /srv
cd /srv
# Retrieve metadata
curl http://metadata/computeMetadata/v1/instance/attributes/vm1-launch-vm2-code -H "Metadata-Flavor: Google" > vm1-launch-vm2-code.py
curl http://metadata/computeMetadata/v1/instance/attributes/service-credentials -H "Metadata-Flavor: Google" > service-credentials.json
# Install dependencies
apt-get update
apt-get install -y python3-pip
pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
# Run VM2 creation script
python3 vm1-launch-vm2-code.py
"""

config_vm1 = {
    "name": VM1_NAME,
    "machineType": f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
    "disks": [
        {
            "boot": True,
            "autoDelete": True,
            "initializeParams": {
                "sourceImage": compute.images().getFromFamily(
                    project=IMAGE_PROJECT, family=IMAGE_FAMILY).execute()["selfLink"]
            }
        }
    ],
    "networkInterfaces": [{
        "network": "global/networks/default",
        "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}]
    }],
    "metadata": {
        "items": [
            {"key": "startup-script", "value": vm1_startup_script},
            {"key": "vm1-launch-vm2-code", "value": vm1_launch_vm2_code},
            {"key": "vm2-startup-script", "value": vm2_startup_script},
            {"key": "service-credentials",
                "value": open("service-credentials.json").read()}
        ]
    }
}

print("Creating VM-1...")
operation = compute.instances().insert(
    project=PROJECT, zone=ZONE, body=config_vm1).execute()

while True:
    result = compute.zoneOperations().get(
        project=PROJECT,
        zone=ZONE,
        operation=operation["name"]).execute()
    if result["status"] == "DONE":
        print("VM-1 created successfully! It will now launch VM-2 internally.")
        break
    time.sleep(5)
