from .db import get_user, api_key_from_login
from .settings import max_api_key_length
from flask import Response
from http.client import UNAUTHORIZED
import re

API_KEY = "api key"
COOKIE = "cookie"
BASIC_AUTH = "basic auth"

token_pattern = r"^Token\s+(.+)$"

# TODO investigate more authz methods:
# - API key in URL


def authenticated_user(request):
    api_key = api_key_from_header(request)
    if api_key:
        return get_user(api_key), API_KEY
    else:
        api_key = api_key_from_cookie(request)
        if api_key:
            return get_user(api_key), COOKIE
    return None, None

def login_user(request):
    api_key = api_key_from_basic_auth(request)
    if api_key:
        return get_user(api_key), BASIC_AUTH
    return None, None


def api_key_from_header(request):
    auth_header = request.headers.get("Authorization", "")[:max_api_key_length]
    match = re.search(token_pattern, auth_header)
    if match:
        api_key = match.group(1)
        return api_key
    return None


def api_key_from_cookie(request):
    return request.cookies.get("api-key", None)


def api_key_from_basic_auth(request):
    authz = request.authorization
    if authz and authz.type == "basic":
        username, password = authz.username, authz.password
        return api_key_from_login(username, password)
    return None


def not_authorized():
    return Response("not authorized", UNAUTHORIZED)
