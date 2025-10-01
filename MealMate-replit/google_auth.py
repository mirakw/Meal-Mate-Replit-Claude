import json
import os

import requests
from database import db
from flask import Blueprint, redirect, request, url_for
from flask_login import login_required, login_user, logout_user
from models import User
from oauthlib.oauth2 import WebApplicationClient

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Get the correct domain - works for both dev and production
replit_domains = os.environ.get("REPLIT_DOMAINS", "")
if replit_domains:
    # REPLIT_DOMAINS can contain multiple domains separated by commas
    domain = replit_domains.split(",")[0].strip()
else:
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "localhost")

REDIRECT_URL = f'https://{domain}/google_login/callback'

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    print(f"""✅ Google OAuth is configured!
Redirect URI: {REDIRECT_URL}

Make sure this redirect URI is whitelisted in your Google Cloud Console:
1. Go to https://console.cloud.google.com/apis/credentials
2. Edit your OAuth 2.0 Client ID
3. Add {REDIRECT_URL} to Authorized redirect URIs

Note: For both dev and production to work, you may need to add both:
- Dev: https://{os.environ.get("REPLIT_DEV_DOMAIN", "")}/google_login/callback
- Prod: https://{replit_domains}/google_login/callback
""")
else:
    print("""⚠️  Google OAuth secrets not found!
Please add GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET to your Replit Secrets.
See: https://docs.replit.com/additional-resources/google-auth-in-flask
""")

client = WebApplicationClient(GOOGLE_CLIENT_ID) if GOOGLE_CLIENT_ID else None

google_auth = Blueprint("google_auth", __name__)


@google_auth.route("/google_login")
def login():
    if not client:
        return "Google OAuth is not configured. Please add GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET to your Replit Secrets.", 500
    
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url.replace("http://", "https://") + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@google_auth.route("/google_login/callback")
def callback():
    if not client:
        return "Google OAuth is not configured.", 500
    
    # Check for errors from Google
    error = request.args.get("error")
    if error:
        error_description = request.args.get("error_description", "Unknown error")
        return f"""
        <h2>Google OAuth Error</h2>
        <p><strong>Error:</strong> {error}</p>
        <p><strong>Description:</strong> {error_description}</p>
        <p>This usually means the redirect URI is not whitelisted in Google Cloud Console.</p>
        <p><strong>Your redirect URI should be:</strong><br>
        <code>{request.base_url.replace("http://", "https://")}</code></p>
        <p><a href="/">Go back home</a></p>
        """, 400
    
    code = request.args.get("code")
    if not code:
        return f"""
        <h2>Missing Authorization Code</h2>
        <p>Google didn't send back an authorization code.</p>
        <p><strong>Make sure this redirect URI is whitelisted in Google Cloud Console:</strong><br>
        <code>{request.base_url.replace("http://", "https://")}</code></p>
        <p>Go to: <a href="https://console.cloud.google.com/apis/credentials">Google Cloud Console</a></p>
        <p><a href="/">Go back home</a></p>
        """, 400
    
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url.replace("http://", "https://"),
        redirect_url=request.base_url.replace("http://", "https://"),
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    userinfo = userinfo_response.json()
    if userinfo.get("email_verified"):
        users_email = userinfo["email"]
        users_name = userinfo.get("given_name", "")
        users_last = userinfo.get("family_name", "")
        users_picture = userinfo.get("picture", "")
    else:
        return "User email not available or not verified by Google.", 400

    user = User.query.filter_by(email=users_email).first()
    if not user:
        user = User(
            email=users_email,
            first_name=users_name,
            last_name=users_last,
            profile_image_url=users_picture,
            oauth_provider="google",
            oauth_id=userinfo.get("sub"),
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()
    else:
        if not user.oauth_provider:
            user.oauth_provider = "google"
            user.oauth_id = userinfo.get("sub")
            db.session.commit()

    login_user(user, remember=True)

    return redirect(url_for("index"))


@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
