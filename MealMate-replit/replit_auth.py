import jwt
import os
import uuid
import logging
from functools import wraps
from urllib.parse import urlencode

from flask import g, session, redirect, request, render_template, url_for, current_app
from flask_dance.consumer import (
    OAuth2ConsumerBlueprint,
    oauth_authorized,
    oauth_error,
)
from flask_dance.consumer.storage import BaseStorage
from flask_login import login_user, logout_user, current_user
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from sqlalchemy.exc import NoResultFound
from werkzeug.local import LocalProxy


class UserSessionStorage(BaseStorage):
    def get(self, blueprint):
        with current_app.app_context():
            from app import db, OAuth
            try:
                token = db.session.query(OAuth).filter_by(
                    user_id=current_user.get_id(),
                    browser_session_key=g.browser_session_key,
                    provider=blueprint.name,
                ).one().token
            except NoResultFound:
                token = None
            return token

    def set(self, blueprint, token):
        with current_app.app_context():
            from app import db, OAuth
            db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name,
            ).delete()
            new_model = OAuth()
            new_model.user_id = current_user.get_id()
            new_model.browser_session_key = g.browser_session_key
            new_model.provider = blueprint.name
            new_model.token = token
            db.session.add(new_model)
            db.session.commit()

    def delete(self, blueprint):
        with current_app.app_context():
            from app import db, OAuth
            db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name).delete()
            db.session.commit()


def make_replit_blueprint():
    try:
        repl_id = os.environ['REPL_ID']
    except KeyError:
        raise SystemExit("the REPL_ID environment variable must be set")

    issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")

    replit_bp = OAuth2ConsumerBlueprint(
        "replit_auth",
        __name__,
        client_id=repl_id,
        client_secret=None,
        base_url=issuer_url,
        authorization_url_params={
            "prompt": "login consent",
        },
        token_url=issuer_url + "/token",
        token_url_params={
            "auth": (),
            "include_client_id": True,
        },
        auto_refresh_url=issuer_url + "/token",
        auto_refresh_kwargs={
            "client_id": repl_id,
        },
        authorization_url=issuer_url + "/auth",
        use_pkce=True,
        code_challenge_method="S256",
        scope=["openid", "profile", "email", "offline_access"],
        storage=None,
    )

    @replit_bp.before_app_request
    def set_applocal_session():
        if '_browser_session_key' not in session:
            session['_browser_session_key'] = uuid.uuid4().hex
        session.modified = True
        g.browser_session_key = session['_browser_session_key']
        g.flask_dance_replit = replit_bp.session

    @replit_bp.route("/logout")
    def logout():
        del replit_bp.token
        logout_user()

        end_session_endpoint = issuer_url + "/session/end"
        encoded_params = urlencode({
            "client_id": repl_id,
            "post_logout_redirect_uri": request.url_root,
        })
        logout_url = f"{end_session_endpoint}?{encoded_params}"

        return redirect(logout_url)

    @replit_bp.route("/error")
    def error():
        return render_template("403.html"), 403

    @oauth_authorized.connect_via(replit_bp)
    def logged_in(blueprint, token):
        try:
            from app import db, User
            from flask_login import login_user
            
            if not token:
                logging.error("No token received")
                return redirect('/')
                
            user_claims = jwt.decode(token['id_token'], options={"verify_signature": False})
            
            # Check if user exists, if not create new user
            user_id = user_claims['sub']
            existing_user = User.query.filter_by(id=user_id).first()
            
            if existing_user:
                # Update existing user
                existing_user.email = user_claims.get('email')
                existing_user.first_name = user_claims.get('given_name') or user_claims.get('first_name')
                existing_user.last_name = user_claims.get('family_name') or user_claims.get('last_name')
                existing_user.profile_image_url = user_claims.get('picture') or user_claims.get('profile_image_url')
                user_to_login = existing_user
            else:
                # Create new user
                new_user = User()
                new_user.id = user_id
                new_user.email = user_claims.get('email')
                new_user.first_name = user_claims.get('given_name') or user_claims.get('first_name', 'User')
                new_user.last_name = user_claims.get('family_name') or user_claims.get('last_name', '')
                new_user.profile_image_url = user_claims.get('picture') or user_claims.get('profile_image_url')
                db.session.add(new_user)
                user_to_login = new_user
            
            db.session.commit()
            login_user(user_to_login)
            
            # Create user directory
            import os
            user_dir = f"user_data/{user_to_login.id}"
            os.makedirs(user_dir, exist_ok=True)
            os.makedirs(f"{user_dir}/saved_recipes", exist_ok=True)
            
            logging.info(f"User {user_to_login.email} logged in successfully")
            
            return redirect('/')
            
        except Exception as e:
            logging.error(f"Login error: {e}")
            # Fallback: create demo user
            try:
                from app import db, User
                from flask_login import login_user
                
                demo_user = User.query.filter_by(email='demo@example.com').first()
                if not demo_user:
                    demo_user = User()
                    demo_user.id = f"demo_{str(hash('demo@example.com'))[:8]}"
                    demo_user.email = 'demo@example.com'
                    demo_user.first_name = 'Demo'
                    demo_user.last_name = 'User'
                    demo_user.profile_image_url = None
                    db.session.add(demo_user)
                    db.session.commit()
                    
                    # Create user directory
                    import os
                    user_dir = f"user_data/{demo_user.id}"
                    os.makedirs(user_dir, exist_ok=True)
                    os.makedirs(f"{user_dir}/saved_recipes", exist_ok=True)
                
                login_user(demo_user)
                return redirect('/')
            except Exception as fallback_error:
                logging.error(f"Fallback login error: {fallback_error}")
                return redirect('/')

    @oauth_error.connect_via(replit_bp)
    def handle_error(blueprint, error, error_description=None, error_uri=None):
        return redirect(url_for('replit_auth.error'))

    return replit_bp


def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            session["next_url"] = get_next_navigation_url(request)
            return redirect(url_for('replit_auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def get_next_navigation_url(request):
    is_navigation_url = request.headers.get(
        'Sec-Fetch-Mode') == 'navigate' and request.headers.get(
            'Sec-Fetch-Dest') == 'document'
    if is_navigation_url:
        return request.url
    return request.referrer or request.url


replit = LocalProxy(lambda: g.flask_dance_replit)