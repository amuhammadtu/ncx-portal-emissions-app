"""Zero-GitHub, Zero-gcloud Pure-Python Cloud Run v2 Deployer (Option 2).

Uses the existing user-space Application Default Credentials
(`%APPDATA%\\gcloud\\application_default_credentials.json`) + `pip_system_certs`
to:
1. Verify Live BigQuery connectivity on `tu-data-edw-pr-1.a113_roadside`.
2. Check Cloud Build & Cloud Run v2 REST API permissions for the active identity.
3. Package the local app directory (`Dockerfile`, `pyproject.toml`, `src/`, `.well-known/`),
   submit a Cloud Build container build, and deploy/update the Cloud Run v2 service
   with `DEFAULT_DATA_MODE=live_bigquery` and Direct IAP (`launchStage=BETA`).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import time
from pathlib import Path

# Ensure user site-packages are on sys.path
for site_dir in [
    Path(r"C:\Users\amuhammad\AppData\Roaming\Python\Python314\site-packages"),
    Path(r"C:\Program Files\Python314\Lib\site-packages"),
]:
    if site_dir.exists() and str(site_dir) not in sys.path:
        sys.path.insert(0, str(site_dir))

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except Exception:
    pass

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery

APP_ROOT = Path(__file__).resolve().parent


def build_source_tarball(root_dir: Path) -> bytes:
    """Create an in-memory .tar.gz archive of the application source for Cloud Build."""
    buf = io.BytesIO()
    include_items = [
        "Dockerfile",
        "pyproject.toml",
        "README.md",
        "AGENTS.md",
        ".well-known",
        "src",
    ]
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in include_items:
            p = root_dir / item
            if p.exists():
                tar.add(str(p), arcname=item)
    return buf.getvalue()


def verify_live_bigquery(project_id: str) -> None:
    """Verify Live BigQuery connectivity to `tu-data-edw-pr-1.a113_roadside`."""
    print(f"[1/4] Verifying Live BigQuery connection to `{project_id}.a113_roadside`...")
    client = bigquery.Client(project=project_id)
    sql = f"""
    SELECT
      COUNT(*) AS recent_rows,
      FORMAT_DATETIME('%Y-%m-%d %H:%M:%S', DATETIME(MAX(record_tstamp), 'Australia/Sydney')) AS latest_aest
    FROM `{project_id}.a113_roadside.ncx_pmcs_airf`
    WHERE record_tstamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    """
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=1024 * 1024 * 1024)
    df = client.query(sql, job_config=job_config).to_dataframe(create_bqstorage_client=False)
    row = df.iloc[0]
    print(
        f"      [OK] Connected to BigQuery! Recent 7d rows: {int(row['recent_rows']):,} | "
        f"Latest Telemetry (AEST): {row['latest_aest']}"
    )


def deploy_via_gcp_rest_api(
    project_id: str,
    bq_project_id: str,
    region: str,
    service_name: str,
    env_name: str,
) -> int:
    """Deploy the local application folder to Cloud Run v2 using GCP REST APIs over ADC."""
    creds, default_proj = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    authed_session = AuthorizedSession(creds)

    # Check active identity
    print(
        f"[2/4] Authenticated via ADC (Hosting Project: `{project_id}` | "
        f"BigQuery EDW Project: `{bq_project_id}`)"
    )

    # Check Cloud Run v2 API accessibility on target project
    run_parent = f"projects/{project_id}/locations/{region}"
    run_list_url = f"https://run.googleapis.com/v2/{run_parent}/services"
    resp = authed_session.get(run_list_url, timeout=30)

    if resp.status_code == 403:
        err_msg = resp.json().get("error", {}).get("message", resp.text)
        print(f"\n[!] Cloud Run IAM / API Notice on project `{project_id}`:")
        print(f"    {err_msg}")
        # Discover other GCP projects accessible to the user where Cloud Run may be enabled
        crm_resp = authed_session.get(
            "https://cloudresourcemanager.googleapis.com/v1/projects", timeout=20
        )
        if crm_resp.status_code == 200:
            projects = crm_resp.json().get("projects", [])
            print(f"\n[i] Accessible GCP Projects for your account ({len(projects)} found):")
            for p in projects:
                pid = p.get("projectId")
                pname = p.get("name")
                pstate = p.get("lifecycleState")
                if pstate == "ACTIVE":
                    # Check if Cloud Run API is enabled on this project
                    r_check = authed_session.get(
                        f"https://run.googleapis.com/v2/projects/{pid}/locations/{region}/services",
                        timeout=10,
                    )
                    run_status = "Cloud Run ENABLED" if r_check.status_code == 200 else f"Cloud Run status={r_check.status_code}"
                    print(f"    - {pid} ({pname}) -> [{run_status}]")
        return 2
    elif resp.status_code != 200:
        print(f"\n[!] Unexpected Cloud Run API response ({resp.status_code}): {resp.text}")
        return 2

    print(f"[3/4] Packaging application source tarball ({APP_ROOT.name})...")
    tar_bytes = build_source_tarball(APP_ROOT)

    # Check IAM permissions and existing Cloud Run services / GCS buckets on target project
    iam_resp = authed_session.post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}:testIamPermissions",
        json={
            "permissions": [
                "run.services.list",
                "run.services.create",
                "run.services.update",
                "cloudbuild.builds.create",
                "storage.buckets.list",
                "storage.buckets.create",
                "storage.objects.create",
            ]
        },
        timeout=20,
    )
    granted_perms = iam_resp.json().get("permissions", []) if iam_resp.status_code == 200 else []
    print(f"      Granted permissions on `{project_id}`: {granted_perms}")

    existing_services = resp.json().get("services", [])
    if existing_services:
        print(f"      Existing Cloud Run services in `{project_id}` ({region}):")
        for s in existing_services:
            print(f"        - {s.get('name')} -> {s.get('uri')} (creator={s.get('creator')}, lastModifier={s.get('lastModifier')})")
            containers = s.get("template", {}).get("containers", [])
            for c in containers:
                print(f"          image: {c.get('image')}")

    # Check Cloud Build history to see what bucket / repo is used in this project
    cb_list = authed_session.get(
        f"https://cloudbuild.googleapis.com/v1/projects/{project_id}/builds?pageSize=5",
        timeout=20,
    )
    if cb_list.status_code == 200:
        builds = cb_list.json().get("builds", [])
        print(f"      Recent Cloud Builds in `{project_id}`: {len(builds)} found")
        for b in builds:
            src = b.get("source", {})
            print(f"        - Build {b.get('id')} ({b.get('status')}): source={src} images={b.get('images')}")
    else:
        print(f"      Cloud Build list status ({cb_list.status_code}): {cb_list.text[:300]}")

    # Discover existing buckets or create staging bucket
    preferred_buckets = [
        f"run-sources-{project_id}-{region}",
        f"{project_id}_cloudbuild",
    ]
    bucket_name = preferred_buckets[0]
    bkt_list = authed_session.get(
        f"https://storage.googleapis.com/storage/v1/b?project={project_id}", timeout=20
    )
    if bkt_list.status_code == 200:
        buckets = [b.get("name") for b in bkt_list.json().get("items", [])]
        if buckets:
            print(f"      Existing GCS buckets in `{project_id}`: {buckets}")
            for pb in preferred_buckets:
                if pb in buckets:
                    bucket_name = pb
                    print(f"      Using Cloud Run source staging bucket `gs://{bucket_name}`...")
                    break

    if "run.services.create" not in granted_perms:
        print(
            f"\n[!] IAM Role Required on `{project_id}` for Direct Cloud Run Deployment:\n"
            f"    Your account currently has read/viewer permissions {granted_perms} on `{project_id}`.\n"
            f"    To deploy services directly via Option 2 (`deploy_direct.ps1`), request the following IAM roles\n"
            f"    on `{project_id}` (or the new SEAL app-hosting project from Epic ENG-2075):\n"
            f"      - roles/run.developer (Cloud Run Developer)\n"
            f"      - roles/cloudbuild.builds.editor (Cloud Build Editor)\n"
            f"      - roles/storage.admin (or write access to `gs://{bucket_name}`)\n"
            f"      - roles/iam.serviceAccountUser (Service Account User on runtime SA)"
        )
        return 2

    object_name = f"source/{int(time.time())}-{service_name}.tar.gz"

    # Ensure staging bucket exists (create if missing)
    bkt_check = authed_session.get(
        f"https://storage.googleapis.com/storage/v1/b/{bucket_name}", timeout=20
    )
    if bkt_check.status_code == 404:
        print(f"      Creating Cloud Build staging bucket `gs://{bucket_name}` in `{region}`...")
        create_bkt_resp = authed_session.post(
            f"https://storage.googleapis.com/storage/v1/b?project={project_id}",
            json={"name": bucket_name, "location": region},
            timeout=30,
        )
        if create_bkt_resp.status_code not in (200, 201):
            print(f"      [!] Bucket creation response ({create_bkt_resp.status_code}): {create_bkt_resp.text}")

    # Upload source tarball to staging bucket
    upload_url = (
        f"https://storage.googleapis.com/upload/storage/v1/b/{bucket_name}/o"
        f"?uploadType=media&name={object_name}"
    )
    up_resp = authed_session.post(
        upload_url,
        data=tar_bytes,
        headers={"Content-Type": "application/gzip"},
        timeout=60,
    )
    if up_resp.status_code not in (200, 201):
        print(f"[!] Could not upload source tarball to gs://{bucket_name}/{object_name}: {up_resp.text}")
        return 2

    # Ensure Artifact Registry repo `cloud-run-source-deploy` exists
    ar_parent = f"projects/{project_id}/locations/{region}"
    ar_repo_url = f"https://artifactregistry.googleapis.com/v1/{ar_parent}/repositories/cloud-run-source-deploy"
    ar_check = authed_session.get(ar_repo_url, timeout=20)
    if ar_check.status_code == 404:
        print(f"      Creating Artifact Registry repository `cloud-run-source-deploy` in `{region}`...")
        authed_session.post(
            f"https://artifactregistry.googleapis.com/v1/{ar_parent}/repositories?repositoryId=cloud-run-source-deploy",
            json={"format": "DOCKER", "description": "Cloud Run Source Deployments"},
            timeout=30,
        )
        time.sleep(5)

    image_tag = f"{region}-docker.pkg.dev/{project_id}/cloud-run-source-deploy/{service_name}:latest"
    print(f"[4/4] Triggering Cloud Build for `{image_tag}`...")
    # Submit to global or regional Cloud Build endpoint
    build_url = f"https://cloudbuild.googleapis.com/v1/projects/{project_id}/builds"
    build_body = {
        "source": {
            "storageSource": {
                "bucket": bucket_name,
                "object": object_name,
            }
        },
        "steps": [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["build", "-t", image_tag, "."],
            },
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["push", image_tag],
            },
        ],
        "images": [image_tag],
    }
    b_resp = authed_session.post(build_url, json=build_body, timeout=30)
    if b_resp.status_code not in (200, 201):
        print(f"[!] Cloud Build submission failed ({b_resp.status_code}): {b_resp.text}")
        return 2

    build_op = b_resp.json()
    build_id = build_op.get("metadata", {}).get("build", {}).get("id", "unknown")
    print(f"      [OK] Cloud Build started (Build ID: `{build_id}`). Polling build completion...")

    for _ in range(60):
        time.sleep(5)
        status_resp = authed_session.get(
            f"https://cloudbuild.googleapis.com/v1/projects/{project_id}/builds/{build_id}",
            timeout=20,
        )
        if status_resp.status_code == 200:
            b_state = status_resp.json().get("status", "UNKNOWN")
            print(f"      ... Cloud Build status: {b_state}")
            if b_state == "SUCCESS":
                break
            if b_state in ("FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED"):
                print(f"[!] Cloud Build failed: {json.dumps(status_resp.json(), indent=2)}")
                return 2

    print("      [OK] Container image built! Deploying Cloud Run v2 service...")
    service_Payload = {
        "launchStage": "BETA",
        "ingress": "INGRESS_TRAFFIC_ALL",
        "template": {
            "sessionAffinity": True,
            "scaling": {"minInstanceCount": 0, "maxInstanceCount": 5},
            "containers": [
                {
                    "image": image_tag,
                    "ports": [{"name": "http1", "containerPort": 8080}],
                    "resources": {"limits": {"cpu": "1", "memory": "1Gi"}},
                    "env": [
                        {"name": "APP_NAME", "value": service_name},
                        {"name": "APP_ENV", "value": env_name},
                        {"name": "GCP_PROJECT_ID", "value": bq_project_id},
                        {"name": "BQ_LOCATION", "value": region},
                        {"name": "DEFAULT_DATA_MODE", "value": "live_bigquery"},
                        {"name": "ALLOW_LOCAL_DEV_AUTH", "value": "true"},
                    ],
                }
            ],
        },
    }
    create_url = f"https://run.googleapis.com/v2/{run_parent}/services?serviceId={service_name}"
    c_resp = authed_session.post(create_url, json=service_Payload, timeout=30)
    if c_resp.status_code == 409:
        patch_url = f"https://run.googleapis.com/v2/{run_parent}/services/{service_name}"
        c_resp = authed_session.patch(patch_url, json=service_Payload, timeout=30)

    if c_resp.status_code not in (200, 201):
        print(f"[!] Cloud Run deployment failed ({c_resp.status_code}): {c_resp.text}")
        return 2

    # Wait briefly for Cloud Run operation to populate service URI
    time.sleep(5)
    svc_get = authed_session.get(
        f"https://run.googleapis.com/v2/{run_parent}/services/{service_name}", timeout=20
    )
    svc_data = svc_get.json() if svc_get.status_code == 200 else c_resp.json()
    uri = svc_data.get("uri", f"https://{service_name}-{project_id}.{region}.run.app")
    print(f"\n[SUCCESS] Deployed `{service_name}` to Cloud Run v2: {uri}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Option 2 Pure-Python Cloud Run v2 Deployer")
    parser.add_argument("--project-id", default="tu-roads-watertreatment-sb-1")
    parser.add_argument("--bq-project-id", default="tu-data-edw-pr-1")
    parser.add_argument("--region", default="australia-southeast1")
    parser.add_argument("--service-name", default="ncx-portal-emissions-app")
    parser.add_argument("--env", default="dev")
    args = parser.parse_args()

    verify_live_bigquery(args.bq_project_id)
    return deploy_via_gcp_rest_api(
        project_id=args.project_id,
        bq_project_id=args.bq_project_id,
        region=args.region,
        service_name=args.service_name,
        env_name=args.env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
