from . import settings
from dataclasses import dataclass
from os import environ
from os.path import isfile
from typing import Union
import bcrypt
import random
import sqlite3
import uuid


@dataclass
class User:
    user_id: int
    name: str
    password_hash: str


@dataclass
class ApiKey:
    policy: str
    policy_data: str
    key: str
    user: User


authz_db_salt = bcrypt.gensalt()
SALT_FILE_NAME = environ.get("AUTHZ_SALT_FILE", "salt-value")


def load_salt():
    global authz_db_salt
    if isfile(SALT_FILE_NAME):
        with open(SALT_FILE_NAME, "rb") as salt:
            authz_db_salt = salt.read()
    else:
        with open(SALT_FILE_NAME, "wb") as salt:
            salt.write(authz_db_salt)
    return authz_db_salt


def get_api_keys(user_id):
    connection = sqlite3.connect("authorization.db")
    with connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM ApiKey WHERE UserId = ?", (user_id,))
        user = cursor.fetchall()


def create_user(username: str, login: bool, retry=100):
    user_id = random.randint(1000000000, 9999999999)
    password = str(uuid.uuid4()) if login else None
    password_hash = (
        bcrypt.hashpw(password.encode("utf-8"), authz_db_salt) if login else None
    )

    connection = sqlite3.connect("authorization.db")

    with connection:
        try:
            connection.execute(
                "INSERT INTO User (Id, Username, PasswordHash) VALUES (?,?,?)",
                (user_id, username, password_hash),
            )
            return (User(user_id, username, password_hash), password)
        except sqlite3.IntegrityError:
            # retry in case violation of unique constraint with user id or api key
            if retry > 0:
                return create_user(username, login, retry=retry - 1)
            else:
                raise


def get_user(api_key: str) -> Union[User, None]:

    with sqlite3.connect("authorization.db") as connection:
        cursor = connection.cursor()
        cursor.execute(
            """SELECT Id, Username, PasswordHash FROM User 
               WHERE ApiKey = (SELECT LIMIT 1 Key FROM ApiKey WHERE Key = ?)""", 
               (api_key,))
        
        user = cursor.fetchone()
        return user and User(user[0], user[1], user[2])


def rotate_api_key(user: User, retry=100) -> str:
    new_api_key = str(uuid.uuid4())
    connection = sqlite3.connect("authorization.db")
    try:
        with connection:
            connection.execute(
                "UPDATE ApiKey SET Key = ? WHERE Id = ?", (new_api_key, user.user_id)
            )
    except sqlite3.IntegrityError:
        if retry > 0:
            return rotate_api_key(user, retry - 1)
        raise

    return new_api_key


def api_key_from_login(username: str, password: str):
    password_hash = password_hash = bcrypt.hashpw(
        password.encode("utf-8"), authz_db_salt
    )
    connection = sqlite3.connect("authorization.db")
    with connection:
        cursor = connection.cursor()
        cursor.execute(
            """
          SELECT Key FROM ApiKey
          WHERE UserId = (SELECT LIMIT 1 Id FROM User WHERE Username = ? AND PasswordHash = ?)
        """,
            (username, password_hash),
        )
        result = cursor.fetchone()
        return result and result[0] or None


def create_api_key(user_id, policy_id=1, policy_data=None):
    key = str(uuid.uuid4())
    with sqlite3.connect("authorization.db") as conn:
        conn.execute(
            "INSERT INTO ApiKey (UserId, PolicyId, PolicyData, Key) VALUES (?,?,?,?)",
            (user_id, policy_id, policy_data, key),
        )

        cursor = conn.cursor()
        cursor.execute(
            """ 
            SELECT p.PolicyName, a.PolicyData, a.Key, u.Id, u.Username, u.PasswordHash FROM ApiKey a
            INNER JOIN User u ON a.UserId = u.Id
            INNER JOIN Policy p ON p.Id = a.PolicyId
            WHERE a.key = ?""",
            (key,),
        )

        (
            policy_name,
            policy_data,
            api_key,
            user_id,
            username,
            password_hash,
        ) = cursor.fetchone()

        return ApiKey(
            policy_name, policy_data, api_key, User(user_id, username, password_hash)
        )


def make_db():
    connection = sqlite3.connect("authorization.db")
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS User (
                Id INT NOT NULL PRIMARY KEY,
                Username TEXT UNIQUE,
                PasswordHash TEXT
                )"""
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS POLICY (
                Id INT PRIMARY KEY,
                PolicyName TEXT NOT NULL,
                PolicyType TEXT NOT NULL --we don't think it will change much, unnormalized for now        
            )"""
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ApiKey (
                Id INT PRIMARY KEY,
                UserId INT,
                PolicyId INT,
                PolicyData TEXT,
                Key TEXT NOT NULL UNIQUE,
                FOREIGN KEY (UserId) REFERENCES User(Id),
                FOREIGN KEY (PolicyId) REFERENCES POLICY(Id)
            )
        """
        )

        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS User_Index ON ApiKey(UserId)"
        )

        create_default_policies()

type_lifecycle = "LC"

policies = [
    ("Use Forever", type_lifecycle),
    ("Use Until", type_lifecycle),
    ("Use Once Before", type_lifecycle),
    ("Rotate Every", type_lifecycle),
]


    with sqlite3.connect("authorization.db") as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM Policy")
        cnt = cursor.fetchone()
        if cnt == 0:
            for name, t in policies:
                connection.execute(
                    "INSERT INTO Policy (PolicyName, PolicyType) VALUES (?,?)",
                    (name, t),
                )
