import uuid
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Endpoints & constants
# ---------------------------------------------------------------------------
GRAPHQL_URL = "https://web.prod.cloud.netflix.com/graphql"
LANDING_URL = "https://www.netflix.com/ph-en/"

RECAPTCHA_SITE_KEY = "6LdqW_EqAAAAAO87Fb_kcZfNzs0IqJRcKiJDYpUv"
INIT_QUERY_ID = "5d76d6a0-ccfe-4c31-b587-b4e1954732ca"
UPDATE_QUERY_ID = "0fd81de7-07af-4c7d-802f-0f4ea4181aa3"

DEFAULT_NFVDID = (
    "BQFmAAEBEHd71oHfkM7FU_oofLECV31AjKJNl9T0lBwR96xzXmWutUqrRdHCkAN1hcHjRlxLI8Eay"
    "T3bVFbyZDu8hLHeBXCz1dcwGebHrzm-7Ty5ckJTvQ%3D%3D"
)

class TrialSender:
    def __init__(self, email: str, nfvdid: str):
        self.email = email
        self.locale = "en-IN"
        self.nfvdid = nfvdid
        self.flwssn = str(uuid.uuid4())
        self.req_id = str(uuid.uuid4())
        self.top_uuid = str(uuid.uuid4())
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://www.netflix.com",
            "Referer": "https://www.netflix.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "x-netflix.request.id": self.req_id,
            "x-netflix.request.toplevel.uuid": self.top_uuid,
            "x-netflix.request.clcs.bucket": "high",
            "x-netflix.context.form-factor": "phone",
            "x-netflix.context.app-version": "v38c5b0da",
            "x-netflix.context.locales": "en-in",
        }

    def cookie_header(self) -> str:
        return f"nfvdid={self.nfvdid}; flwssn={self.flwssn}"

    def _headers_with_cookie(self) -> dict:
        headers = self._headers.copy()
        headers["Cookie"] = self.cookie_header()
        return headers

    def payload_init(self) -> dict:
        return {
            "operationName": "CLCSWebInitSignup",
            "variables": {
                "inputNode": "WELCOME",
                "locale": self.locale,
                "inputFields": [
                    {"name": "flwssn", "value": {"stringValue": self.flwssn}},
                    {"name": "email", "value": {"stringValue": self.email}},
                    {"name": "recaptchaError", "value": {"stringValue": "LOAD_TIMED_OUT"}},
                    {"name": "recaptchaResponseTime", "value": {}},
                    {"name": "recaptchaSiteKey", "value": {"stringValue": RECAPTCHA_SITE_KEY}},
                    {"name": "recaptchaToken", "value": {}},
                ],
            },
            "extensions": {"persistedQuery": {"id": INIT_QUERY_ID, "version": 102}},
        }

    def payload_update(self) -> dict:
        return {
            "operationName": "CLCSScreenUpdate",
            "variables": {
                "format": "HTML",
                "imageFormat": "PNG",
                "locale": self.locale,
                "serverState": "Bgjru+vcAxLTAf/qOOEwXPLVxW+7Jod9WpjYuKN8j1qfhQpzCK4mmQts5eMSeaP+l7s6NKcNBO4rmYabFFCVnMpCH3ib4AicvXAKm30Z+s5W3Cst0D0BK5x/pwn3QmByi/OgGwU/fzaiR5oxSlZe4fKVexWHISkE4GMzJqLaaXQR0M73ynZB9idNBfqsz3RA5WJN+DGAbVUOZlWl8eZqffvQpp/5MGubeQFpdwKqkAx1nHh7/xI1i9tDU0KLgrvkZrbe6nQ1MX2nc9TBxqnVVxtc3ptHdqydP1wlIu0YBiIOCgydgLg1SvK6tSPOff8=",
                "serverScreenUpdate": "Bgjru+vcAxKSAjDnHOxlaIbFSbwaWzZo/REHFnNG7OtpcXdKTDlcL4/o+huGi/fNW+jrqNDqDSsv1iytiG/ZtvO9ierUE9M1Kc/yEj9JsSiG3XpPciFDzPd6psSaG68XLbos+Qie0wniXCtJyWDLDuLd9ayCMB8qGCxwbov6B41kCQY/zArwlecm0GNoJdd5jvZfBJVtytD6mMCYnPA/9zhX4okj+6IGet9xOCYt76IDiuyESxgKbaOLcd6DQIDSBf4m/lYi2Tasj7olPkCaDIXxjU+0UY+b7eDyhvi2if2vt6510ARrGsSZq8DaazQmrpAbfiCW47s1/1mR59vUMYeT8VCqqAvbNwipqyP1DQMHtoTnCoWns0+x6IgYBiIOCgx9EW4i3i9SUswnHEg=",
                "inputFields": [
                    {"name": "email", "value": {"stringValue": self.email}},
                    {"name": "pipcConsent", "value": {"booleanValue": False}},
                ],
            },
            "extensions": {"persistedQuery": {"id": UPDATE_QUERY_ID, "version": 102}},
        }

    async def check_banner(self):
        headers = self._headers_with_cookie()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(LANDING_URL, headers=headers)

        if 'data-uia="free-trial-banner"' in resp.text or "Try 30 days" in resp.text:
            banner = ""
            marker = 'data-uia="free-trial-banner-text"'
            i = resp.text.find(marker)
            if i != -1:
                j = resp.text.find("</p>", i)
                if j != -1:
                    banner = resp.text[i:j].split(">", 1)[-1]
            return banner or "30-day trial"
        return None

    async def send_signup(self):
        headers = self._headers_with_cookie()
        async with httpx.AsyncClient(timeout=30) as client:
            resp1 = await client.post(GRAPHQL_URL, json=self.payload_init(), headers=headers)
            if '"errors"' in resp1.text.lower():
                return False, f"Signup rejected (HTTP {resp1.status_code})"

            resp2 = await client.post(GRAPHQL_URL, json=self.payload_update(), headers=headers)
            if resp2.status_code == 200 and '"errors"' not in resp2.text.lower():
                return True, "Trial activated successfully."
            
            return False, f"Signup failed (HTTP {resp2.status_code})"

# ---------------------------------------------------------------------------
# Starlette App Routes
# ---------------------------------------------------------------------------
async def home(request):
    return JSONResponse({"message": "API is running. Send a POST request to /process-trial"})

async def process_trial(request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "failed", "message": "Invalid JSON payload."}, status_code=400)
    
    email = data.get("email")
    if not email or "@" not in email:
        return JSONResponse({"status": "failed", "message": "Invalid email address."}, status_code=400)
    
    nfvdid = data.get("nfvdid", DEFAULT_NFVDID)
    
    sender = TrialSender(email=email, nfvdid=nfvdid)
    banner = await sender.check_banner()

    if banner and "30" in banner.lower():
        success, message = await sender.send_signup()
        if success:
            return JSONResponse({"status": "success", "email": email, "message": message})
        else:
            return JSONResponse({"status": "failed", "email": email, "message": message})
    else:
        return JSONResponse({
            "status": "failed", 
            "email": email, 
            "message": "30 Days Trial Not Detected. Please provide a new nfvdid."
        })

# Dito natin in-add ang CORS rules para payagan ang mga requests mula kahit saang website (gaya ng iyong test.html)
middleware = [
    Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
]

app = Starlette(debug=True, routes=[
    Route('/', home, methods=['GET']),
    Route('/process-trial', process_trial, methods=['POST']),
], middleware=middleware)
