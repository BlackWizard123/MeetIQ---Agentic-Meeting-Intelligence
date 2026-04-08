"""
Shared token loader — works both locally and on Cloud Run.
Local:     reads backend/token.json
Cloud Run: reads from Secret Manager (GOOGLE_TOKEN secret)
"""
import os, json

def load_token() -> dict:
    if os.getenv("K_SERVICE"):
        # Running on Cloud Run — load from Secret Manager
        from google.cloud import secretmanager
        client  = secretmanager.SecretManagerServiceClient()
        project = os.getenv("GCP_PROJECT")
        name    = f"projects/{project}/secrets/GOOGLE_TOKEN/versions/latest"
        resp    = client.access_secret_version(request={"name": name})
        return json.loads(resp.payload.data.decode("UTF-8"))
    else:
        # Local dev — load from file
        token_path = os.path.join(os.path.dirname(__file__), "../token.json")
        with open(token_path) as f:
            return json.load(f)