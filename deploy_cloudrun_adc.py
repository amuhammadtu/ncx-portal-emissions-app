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
    print(f"[2/4] Authenticated via ADC (Quota/Default Project: `{default_proj or project_id}`)")

    # Check Cloud Run v2 API accessibility on target project
    run_parent = f"projects/{project_id}/locations/{region}"
    run_list_url = f"https://run.googleapis.com/v2/{run_parent}/services"
    resp = authed_session.get(run_list_url, timeout=30)

    if resp.status_code == 403:
        err_msg = resp.json().get("error", {}).get("message", resp.text)
        print(f"\n[!] Cloud Run IAM Notice on project `{project_id}`:")
        print(f"    {err_msg}")
        print("\n    Why this happened:")
        print(
            f"    - Your ADC token has full read/query access to `{project_id}.a113_roadside` (BigQuery),\n"
            f"      which is an EDW data warehouse project, whereas Cloud Run app hosting requires\n"
            f"      `roles/run.admin` + `roles/cloudbuild.builds.editor` in your app-hosting project\n"
            f"      (tracked as Issue I1 in Epic ENG-2075: `tu-data-apps-dev` vs `{project_id}`)."
        )
        return 2
    elif resp.status_code != 200:
        print(f"\n[!] Unexpected Cloud Run API response ({resp.status_code}): {resp.text}")
        return 2

    print(f"[3/4] Packaging application source tarball ({APP_ROOT.name})...")
    tar_bytes = build_source_tarball(APP_ROOT)
    bucket_name = f"{project_id}_cloudbuild"
    object_name = f"source/{int(time.time())}-{service_name}.tar.gz"

    # Ensure staging bucket exists or upload to it
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

    image_tag = f"{region}-docker.pkg.dev/{project_id}/cloud-run-source-deploy/{service_name}:latest"
    print(f"[4/4] Triggering Cloud Build for `{image_tag}`...")
    build_url = f"https://cloudbuild.googleapis.com/v1/projects/{project_id}/locations/{region}/builds"
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

    print("      [OK] Cloud Build submitted! Deploying Cloud Run v2 service...")
    service_Payload = {
        "launchStage": "BETA",
        "ingress": "INGRESS_TRAFFIC_ALL",
        "iapEnabled": True,
        "template": {
            "sessionAffinity": True,
            "scaling": {"minInstanceCount": 0, "maxInstanceCount": 5},
            "containers": [
                {
                    "image": image_tag,
                    "ports": [{"name": "http1", "containerPort": 8080}],
                    "env": [
                        {"name": "APP_NAME", "value": service_name},
                        {"name": "APP_ENV", "value": env_name},
                        {"name": "GCP_PROJECT_ID", "value": project_id},
                        {"name": "BQ_LOCATION", "value": region},
                        {"name": "DEFAULT_DATA_MODE", "value": "live_bigquery"},
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

    svc_data = c_resp.json()
    uri = svc_data.get("uri", f"https://{service_name}-{project_id}.{region}.run.app")
    print(f"\n[SUCCESS] Deployed `{service_name}` to Cloud Run v2: {uri}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Option 2 Pure-Python Cloud Run v2 Deployer")
    parser.add_argument("--project-id", default="tu-data-edw-pr-1")
    parser.add_argument("--region", default="australia-southeast1")
    parser.add_argument("--service-name", default="ncx-portal-emissions-app")
    parser.add_argument("--env", default="dev")
    args = parser.parse_args()

    verify_live_bigquery(args.project_id)
    return deploy_via_gcp_rest_api(
        project_id=args.project_id,
        region=args.region,
        service_name=args.service_name,
        env_name=args.env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
