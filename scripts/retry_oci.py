#!/usr/bin/env python3
"""Retry an existing OCI Resource Manager stack only after capacity failures."""
import os
import sys
import time
import oci

STACK_ID = os.environ["OCI_STACK_OCID"]
COMPARTMENT = os.environ["OCI_COMPARTMENT_OCID"]
TARGET = os.environ["OCI_INSTANCE_NAME"]
CAPACITY_TERMS = ("out of capacity", "outofhostcapacity", "out of host capacity", "capacity unavailable", "insufficient capacity", "out of capacity for shape")

def config():
    key = os.environ["OCI_PRIVATE_KEY"].replace("\\n", "\n")
    path = "/tmp/oci_key.pem"
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    os.chmod(path, 0o600)
    cfg = {
        "user": os.environ["OCI_USER_OCID"],
        "fingerprint": os.environ["OCI_FINGERPRINT"],
        "tenancy": os.environ["OCI_TENANCY_OCID"],
        "region": os.environ.get("OCI_REGION", "ap-mumbai-1"),
        "key_file": path,
    }
    oci.config.validate_config(cfg)
    return cfg

def main():
    cfg = config()
    compute = oci.core.ComputeClient(cfg)
    rm = oci.resource_manager.ResourceManagerClient(cfg)
    instances = oci.pagination.list_call_get_all_results(
        compute.list_instances, COMPARTMENT).data
    matches = [i for i in instances if i.display_name == TARGET and i.lifecycle_state != "TERMINATED"]
    if any(i.lifecycle_state == "RUNNING" for i in matches):
        print("SUCCESS: target instance is RUNNING; no further apply.")
        return 0
    if matches:
        print("Instance already exists but is not RUNNING; not creating a duplicate.")
        return 0

    jobs = oci.pagination.list_call_get_all_results(rm.list_jobs, stack_id=STACK_ID).data
    applies = sorted(
        (j for j in jobs if str(j.operation).upper() == "APPLY"),
        key=lambda j: j.time_created or oci.util.parse_datetime("1970-01-01T00:00:00+00:00"),
        reverse=True,
    )
    if applies:
        latest = applies[0]
        state = str(latest.lifecycle_state).upper()
        print(f"Latest APPLY job {latest.id}: {state}")
        if state in ("ACCEPTED", "IN_PROGRESS", "CANCELING"):
            print("Apply already underway; skip.")
            return 0
        if state == "SUCCEEDED":
            print("Previous apply succeeded, but target VM was not found. Manual investigation required.")
            return 1
        if state != "FAILED":
            print("Unexpected job state; not retrying.")
            return 1
        logs = oci.pagination.list_call_get_all_results(
            rm.list_job_logs, latest.id).data
        message = "\n".join(str(getattr(log, "message", "")) for log in logs).lower()
        if not any(term in message for term in CAPACITY_TERMS):
            print("Last failure is not confirmed to be a capacity failure; no retry.")
            return 1
        print("Confirmed capacity failure; safe to retry.")
    else:
        print("No prior APPLY job found. Initial apply requires manual approval.")
        return 1

    details = oci.resource_manager.models.CreateJobDetails(
        stack_id=STACK_ID,
        job_operation_details=oci.resource_manager.models.CreateApplyJobOperationDetails(
            execution_plan_strategy="AUTO_APPROVED"))
    response = rm.create_job(details)
    print(f"Created APPLY job: {response.data.id}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"OCI operation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
