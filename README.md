# Oracle yct-driver capacity retries

This repository contains a GitHub Actions schedule that checks the **existing** Oracle Resource Manager stack every 15 minutes. It only launches a new APPLY after the latest APPLY job failed with a recognized host-capacity error. It does not create new stacks, modify availability domains, or run concurrent applies.

## GitHub configuration

In Settings → Secrets and variables → Actions, create these **repository secrets**:
- `OCI_TENANCY_OCID`: tenancy OCID
- `OCI_USER_OCID`: OCI API-key user's OCID
- `OCI_FINGERPRINT`: uploaded API public-key fingerprint
- `OCI_PRIVATE_KEY`: complete PEM private key, including BEGIN/END lines
- `OCI_STACK_OCID`: OCID of existing yct-driver stack
- `OCI_COMPARTMENT_OCID`: compartment containing the VM

Under **Variables**, add `OCI_INSTANCE_NAME`: exact display name of the VM specified in the stack's Terraform configuration.

Region is configured as `ap-mumbai-1` in the workflow.

Use a dedicated OCI IAM user with minimal permissions. Never commit the private key, an OCI config file, or a Terraform state file.

## Starting

Run an initial APPLY manually from OCI Resource Manager, if no previous APPLY exists. Then open Actions → Oracle A1 capacity retry → Run workflow to test. Failed capacity attempts will be retried on the schedule. If a job is still running, the next scheduled check skips it.

When the target instance is RUNNING, future scheduled checks perform no APPLY; they still run lightweight status checks. To stop GitHub scheduled runs entirely, disable the workflow in GitHub Actions after success.

## Important limitations

GitHub cron is best-effort and may be delayed. Only recognized capacity failures are retried; all other failures require investigation. If the stack creates an instance with a different display name, the checker will refuse to retry after a successful APPLY. This automation never destroys resources or modifies Terraform configuration. Free-tier eligibility and charges must be checked separately in Oracle Cloud.
