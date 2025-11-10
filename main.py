import os
import time
import json
import re
import subprocess
import shutil
import requests
import schedule
import urllib3
import random
import string
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Optional, Dict, Any

urllib3.disable_warnings()
load_dotenv()

# ---------- Configuration ----------
API_KEY = os.getenv("MSP_API_KEY")
BASE_URL = os.getenv("MSP_BASE_URL", "https://support.arche.global:8448/api/v3/requests")
HEADERS = {
    "TECHNICIAN_KEY": API_KEY,
    "Content-Type": "application/x-www-form-urlencoded"
}

# Terraform / filesystem
TF_DIR = "./terraform"
TF_GENERATED_DIR = os.path.join(TF_DIR, "generated")
STATE_FILE = "processed_requests.json"

# Graph API config
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")
GRAPH_SENDER_EMAIL = os.getenv("GRAPH_SENDER_EMAIL")

# Timeouts and retries
HTTP_TIMEOUT = 15
HTTP_RETRIES = 3
RETRY_BACKOFF = 2

# Required UDFs
REQUIRED_UDFS = [
    "OS_Type",
    "CPU Size",
    "Disk Size",
    "Region or Location to host VM",
    "Resource Group",
    "OS Name",
    "OS Version"
]

# Disk mapping
DISK_MAP = {
    "standard_hdd": "Standard_LRS",
    "standard_lrs": "Standard_LRS",
    "standard_ssd": "StandardSSD_LRS",
    "standardssd_lrs": "StandardSSD_LRS",
    "premium_ssd": "Premium_LRS",
    "premium_lrs": "Premium_LRS",
    "standard_hdd_lrs": "Standard_LRS",
    "standard_ssd_lrs": "StandardSSD_LRS",
    "premium_ssd_lrs": "Premium_LRS"
}

# ---------- Helpers: ANSI Strip ----------
def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# ---------- Helpers: Persistent state ----------
def load_processed_requests() -> set:
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_processed_requests(processed_ids: set):
    with open(STATE_FILE, "w") as f:
        json.dump(list(processed_ids), f, indent=2)

# ---------- Helpers: HTTP with retries ----------
def http_request_with_retries(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            resp = requests.request(method, url, timeout=HTTP_TIMEOUT, verify=False, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"[HTTP] Attempt {attempt}/{HTTP_RETRIES} failed for {url}: {e}")
            if attempt < HTTP_RETRIES:
                time.sleep(RETRY_BACKOFF ** attempt)
            else:
                return getattr(e, "response", None)
    return None

# ---------- MSP API Wrappers ----------
def fetch_open_requests(limit=10):
    params = {
        "input_data": json.dumps({
            "list_info": {
                "row_count": limit,
                "start_index": 1,
                "sort_field": "id",
                "sort_order": "desc",
                "get_total_count": True,
                "search_criteria": [
                    {"field": "status.name", "condition": "is", "values": ["Open"], "logical_operator": "AND"},
                    {"field": "template.id", "condition": "is", "values": ["901"], "logical_operator": "AND"}
                ]
            }
        }),
        "format": "json"
    }
    resp = http_request_with_retries("GET", BASE_URL, headers=HEADERS, params=params)
    if not resp:
        print("[ERROR] Failed to fetch open requests.")
        return []
    try:
        return resp.json().get("requests", [])
    except ValueError:
        print("[ERROR] Invalid JSON fetching open requests:", resp.text)
        return []

def get_request(req_id):
    url = f"{BASE_URL}/{req_id}"
    resp = http_request_with_retries("GET", url, headers=HEADERS, params={"format": "json"})
    if not resp:
        print(f"[ERROR] Failed to GET request {req_id}")
        return None
    try:
        return resp.json().get("request", {})
    except ValueError:
        print(f"[ERROR] Invalid JSON when fetching request {req_id}: {resp.text}")
        return None

def post_worklog(
    req_id: int,
    description: str = "",
    work_hours: int = 0,
    work_minutes: int = 0,
    start_time_ms: Optional[int] = None,
    end_time_ms: Optional[int] = None,
    owner_id: str = "10850",
    is_billable: bool = False,
    include_nonoperational_hours: bool = False,
) -> bool:
    url = f"{BASE_URL}/{req_id}/worklogs"

    def _format_display(ts_ms: int) -> str:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%b %-d, %Y %I:%M %p")

    payload = {
        "worklog": {
            "owner": {
                "id": owner_id,
                "name": "Nova O'Sullivan" if owner_id == "10850" else ""
            },
            "description": description,
            "time_spent": {
                "hours": str(work_hours),
                "minutes": str(work_minutes)
            },
            "is_billable": str(is_billable).lower(),
            "include_nonoperational_hours": include_nonoperational_hours,
            "other_cost": "0.00",
            "type": None
        }
    }

    if start_time_ms is not None:
        payload["worklog"]["start_time"] = {
            "value": start_time_ms,
            "display_value": _format_display(start_time_ms)
        }
    if end_time_ms is not None:
        payload["worklog"]["end_time"] = {"value": end_time_ms}

    data = {"input_data": json.dumps(payload, separators=(",", ":"))}
    resp = http_request_with_retries("POST", url, headers=HEADERS, data=data)

    if resp and resp.status_code in (200, 201):
        print(f"[WORKLOG] Added worklog to {req_id}: {description[:80]}")
        return True
    else:
        print(f"[ERROR] Failed to add worklog to {req_id}: {getattr(resp, 'text', 'no response')}")
        return False

def append_note_to_request(req_id: int, note: str) -> bool:
    url = f"{BASE_URL}/{req_id}/notes"
    payload = {
        "note": {
            "description": note
        }
    }
    data = {"input_data": json.dumps(payload)}
    resp = http_request_with_retries("POST", url, headers=HEADERS, data=data)
    if resp and resp.status_code in (200, 201):
        print(f"[NOTE] Appended note to {req_id}")
        return True
    else:
        print(f"[ERROR] Failed to append note to {req_id}: {getattr(resp, 'text', 'no response')}")
        return False

def update_request_status(req_id: int, new_status: str, closure_code: Optional[str] = None, closure_comments: Optional[str] = None) -> bool:
    url = f"{BASE_URL}/{req_id}"
    req_body = {"status": {"name": new_status}}
    if closure_code:
        req_body["closure_code"] = {"name": closure_code}
    if closure_comments:
        req_body["closure_comments"] = closure_comments

    payload = {"request": req_body}
    data = {"input_data": json.dumps(payload)}
    resp = http_request_with_retries("PUT", url, headers=HEADERS, data=data)
    if resp and resp.status_code == 200:
        print(f"[UPDATE] Request {req_id} status set to '{new_status}'")
        return True
    else:
        print(f"[ERROR] Failed to update Request {req_id} status: {getattr(resp, 'text', 'no response')}")
        return False

def fetch_metainfo_udf_fields():
    url = f"{BASE_URL}/metainfo"
    resp = http_request_with_retries("GET", url, headers=HEADERS)
    if not resp:
        return {}
    try:
        metainfo = resp.json().get("metainfo", {})
        fields = metainfo.get("fields", {}).get("udf_fields", {}).get("fields", {})
        return fields
    except ValueError:
        print("[ERROR] Invalid metainfo JSON")
        return {}

# ---------- Helpers: parsing ----------
def parse_int_from_value(value, default=None):
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if value is None:
        return default
    match = re.search(r"\d+", str(value))
    if match:
        return int(match.group(0))
    return default

def normalize_disk(raw_disk: str) -> str:
    normalized = re.sub(r"\s+", "_", (raw_disk or "").strip()).lower()
    return DISK_MAP.get(normalized, "Standard_LRS")

def generate_random_password(length=14):
    chars = string.ascii_letters + string.digits + "!@#$%&*()-_=+"
    return "".join(random.choice(chars) for _ in range(length))

# ---------- Helpers: Terraform ----------
def ensure_terraform_available() -> Optional[str]:
    terraform_exe = shutil.which("terraform")
    if not terraform_exe:
        print("[ERROR] Terraform not found on PATH.")
        return None
    return terraform_exe

def terraform_init_apply(terraform_exe: str, tfvars_path: str, workdir: str = TF_DIR) -> Dict[str, Any]:
    result = {"success": False, "stdout": "", "stderr": "", "outputs": {}}
    try:
        print("[TERRAFORM] Initializing...")
        init_proc = subprocess.run([terraform_exe, "init", "-input=false"], cwd=workdir,
                                   capture_output=True, text=True)
        result["stdout"] += init_proc.stdout
        result["stderr"] += init_proc.stderr
        if init_proc.returncode != 0:
            print("[ERROR] Terraform init failed.")
            return result

        print("[TERRAFORM] Applying...")
        apply_proc = subprocess.run(
            [terraform_exe, "apply", "-auto-approve", f"-var-file={tfvars_path}"],
            cwd=workdir, capture_output=True, text=True
        )
        result["stdout"] += apply_proc.stdout
        result["stderr"] += apply_proc.stderr
        if apply_proc.returncode != 0:
            print("[ERROR] Terraform apply failed.")
            return result

        print("[TERRAFORM] Fetching outputs...")
        out_proc = subprocess.run([terraform_exe, "output", "-json"], cwd=workdir, capture_output=True, text=True)
        result["stdout"] += out_proc.stdout
        result["stderr"] += out_proc.stderr
        if out_proc.returncode == 0 and out_proc.stdout.strip():
            try:
                result["outputs"] = json.loads(out_proc.stdout)
                result["success"] = True
            except json.JSONDecodeError:
                result["success"] = True
        else:
            result["success"] = True
        return result
    except Exception as e:
        result["stderr"] += str(e)
        return result

# ---------- Microsoft Graph ----------
def get_graph_token():
    if not all([GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID]):
        print("[GRAPH] Missing Graph credentials.")
        return None
    token_url = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": GRAPH_CLIENT_ID,
        "client_secret": GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    try:
        resp = requests.post(token_url, data=data, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[GRAPH] Failed to get token: {e}")
        return None

def send_email_graph(to_address: str, subject: str, body_html: str, token: Optional[str] = None) -> bool:
    if not token:
        token = get_graph_token()
    if not token or not GRAPH_SENDER_EMAIL:
        print("[GRAPH] Missing token or sender email.")
        return False

    url = f"https://graph.microsoft.com/v1.0/users/{GRAPH_SENDER_EMAIL}/sendMail"
    mail = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": to_address}}],
            "from": {"emailAddress": {"address": GRAPH_SENDER_EMAIL}}
        },
        "saveToSentItems": True
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=mail, timeout=HTTP_TIMEOUT)
        if resp.status_code in (200, 202):
            print(f"[GRAPH] Email sent to {to_address}")
            return True
        else:
            print(f"[GRAPH] Failed to send email: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"[GRAPH] Exception sending email: {e}")
        return False

# ---------- Core: Process single request ----------
def process_request(req_id: int) -> bool:
    now_iso = datetime.now(timezone.utc).isoformat(timespec='seconds') + "Z"
    print(f"\n[PROCESS] Starting processing for Request {req_id} at {now_iso}")

    request_data = get_request(req_id)
    if not request_data:
        print(f"[SKIP] Request {req_id} could not be fetched.")
        return False

    metainfo_fields = fetch_metainfo_udf_fields()
    meta_field_mapping = {k: v.get("name") for k, v in metainfo_fields.items() if v.get("name")}
    udf = request_data.get("udf_fields", {}) or {}
    updated_udf = {meta_field_mapping.get(key, key): value for key, value in udf.items()}

    missing = [f for f in REQUIRED_UDFS if not updated_udf.get(f)]
    if missing:
        msg = f"Missing required UDF fields: {missing}"
        print(f"[ERROR] {msg}")
        post_worklog(req_id, f"[ERROR] {msg}")
        return False

    post_worklog(req_id, "Beginning automation: parsing UDFs and preparing Terraform variables.")

    raw_disk = updated_udf.get("Disk Type", "")
    disk_type = normalize_disk(raw_disk)
    print(f"[INFO] Disk mapping: '{raw_disk}' -> '{disk_type}'")

    disk_size_value = parse_int_from_value(updated_udf.get("Disk Size"), default=30)
    number_of_vms_value = parse_int_from_value(updated_udf.get("Number of VMs to be deployed"), default=1)
    if number_of_vms_value <= 0:
        number_of_vms_value = 1

    tfvars = {
        "os_type": updated_udf.get("OS_Type"),
        "environment": updated_udf.get("Environment"),
        "os_version_details": updated_udf.get("OS Version Details"),
        "vm_size": updated_udf.get("CPU Size"),
        "location": updated_udf.get("Region or Location to host VM"),
        "disk_type": disk_type,
        "disk_size": disk_size_value,
        "resource_group": updated_udf.get("Resource Group"),
        "availability_zone": updated_udf.get("Availability Zone"),
        "os_name": updated_udf.get("OS Name"),
        "os_version": updated_udf.get("OS Version"),
        "vm_series": updated_udf.get("VM Series or family"),
        "number_of_vms": number_of_vms_value
    }

    os.makedirs(TF_GENERATED_DIR, exist_ok=True)
    tfvars_path = os.path.join(TF_GENERATED_DIR, f"request_{req_id}.tfvars.json")
    with open(tfvars_path, "w") as f:
        json.dump(tfvars, f, indent=2)

    post_worklog(req_id, "Terraform tfvars generated and saved.", work_minutes=1)

    update_request_status(req_id, "In Progress")
    post_worklog(req_id, "Ticket state changed to In Progress. Starting VM provisioning.")

    terraform_exe = ensure_terraform_available()
    if not terraform_exe:
        err_msg = "[ERROR] Terraform binary not found. Please install & add terraform to PATH."
        print(err_msg)
        post_worklog(req_id, err_msg)
        update_request_status(req_id, "Open")
        return False

    tf_result = terraform_init_apply(terraform_exe, tfvars_path, workdir=TF_DIR)

    # Clean and log output
    stdout_clean = strip_ansi(tf_result.get("stdout", ""))[:8000]
    stderr_clean = strip_ansi(tf_result.get("stderr", ""))[:8000]

    if stdout_clean.strip():
        post_worklog(req_id, f"Terraform stdout:\n{stdout_clean[:4000]}")
    if stderr_clean.strip():
        post_worklog(req_id, f"Terraform stderr:\n{stderr_clean[:4000]}")

    if not tf_result.get("success"):
        err_note = f"Terraform provisioning failed for Request {req_id}. See worklogs for details."
        post_worklog(req_id, f"[ERROR] {err_note}")
        append_note_to_request(req_id, f"[Automation Error] Terraform error at {now_iso}")
        update_request_status(req_id, "Open")
        return False

    # Extract outputs
    outputs = tf_result.get("outputs", {}) or {}
    vm_ip = vm_username = vm_password = None
    for k, v in outputs.items():
        val = v.get("value") if isinstance(v, dict) else v
        key_lower = k.lower()
        if "ip" in key_lower and not vm_ip:
            vm_ip = val
        if key_lower in ("username", "admin_username", "admin_user") and not vm_username:
            vm_username = val
        if key_lower in ("password", "admin_password") and not vm_password:
            vm_password = val

    if not vm_username:
        vm_username = updated_udf.get("OS User", "azureuser")
    if not vm_password:
        vm_password = generate_random_password()

    # Send email
    requester_email = (request_data.get("requester") or {}).get("email_id")
    if requester_email:
        subject = f"VM Provisioned - Request {req_id}"
        body = f"""
        <p>Hello,</p>
        <p>Your VM requested in ticket <strong>{req_id}</strong> has been provisioned.</p>
        <ul>
          <li><strong>IP / DNS:</strong> {vm_ip or 'N/A'}</li>
          <li><strong>Username:</strong> {vm_username}</li>
          <li><strong>Password:</strong> {vm_password}</li>
          <li><strong>OS:</strong> {updated_udf.get('OS Name')} {updated_udf.get('OS Version')}</li>
          <li><strong>Region:</strong> {updated_udf.get('Region or Location to host VM')}</li>
        </ul>
        <p>Please change the password on first login.</p>
        <p>Regards,<br/>Automated Provisioner</p>
        """
        if send_email_graph(requester_email, subject, body):
            post_worklog(req_id, f"Provisioned VM details sent to {requester_email}.", work_minutes=1)
        else:
            post_worklog(req_id, f"[WARN] Failed to send email to {requester_email}.")
    else:
        post_worklog(req_id, "[WARN] Requester email not found; skipping email.")

    closure_comment = f"VM provisioned. IP: {vm_ip or 'N/A'}, Username: {vm_username}"
    post_worklog(req_id, "Provisioning succeeded. Preparing to close ticket.")

    closed = update_request_status(req_id, "Closed", closure_code="Success", closure_comments=closure_comment)
    if not closed:
        post_worklog(req_id, "[WARN] Failed to set ticket to Closed.")
        return False

    post_worklog(req_id, "Ticket closed by automation.", work_minutes=1)
    append_note_to_request(req_id, f"[Automation] Closed at {now_iso}. {closure_comment}")

    print(f"[SUCCESS] Request {req_id} completed and closed.")
    return True

# ---------- Job scheduler ----------
def job():
    print("\n==== Running MSP Terraform Automation ====")
    requests_list = fetch_open_requests(limit=20)
    processed = load_processed_requests()

    if not requests_list:
        print("[INFO] No open requests found.")
        return

    for req in requests_list:
        req_id = req.get("id")
        if not req_id or req_id in processed:
            continue

        try:
            success = process_request(req_id)
            if success:
                processed.add(req_id)
                save_processed_requests(processed)
            else:
                print(f"[INFO] Request {req_id} failed or deferred.")
        except Exception as e:
            print(f"[EXCEPTION] Unhandled error: {e}")
            post_worklog(req_id, f"[EXCEPTION] {e}")
            update_request_status(req_id, "Open")

    print("==== Cycle Complete ====")

# ---------- Main ----------
if __name__ == "__main__":
    print("[INFO] Scheduler starting. Runs every 1 minute.")
    schedule.every(1).minutes.do(job)

    try:
        job()
        while True:
            schedule.run_pending()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[INFO] Scheduler stopped by user.")