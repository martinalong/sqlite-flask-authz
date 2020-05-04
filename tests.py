import requests
import settings
import http
import db

def call_no_header():
    resp = requests.get(settings.endpoint)
    assert(resp.status_code == http.client.UNAUTHORIZED)

def call_incorrect_authentication():
    headers = {'Authorization': 'token: asdfsadfsadfadsfadsfdsafdsaf'}
    resp = requests.get(settings.endpoint, headers = headers)
    assert(resp.status_code == http.client.UNAUTHORIZED)

user, _ = db.create_user("tester", False)

def call_correct_authentication():
    headers = {'Authorization': f'Token {user.api_key}'}
    resp = requests.get(settings.endpoint, headers = headers)
    assert(resp.status_code == http.client.OK)


call_no_header()
call_incorrect_authentication()
call_correct_authentication()
