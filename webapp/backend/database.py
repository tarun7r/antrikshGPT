import json
from pathlib import Path
from typing import Dict, Optional

from webapp.backend.auth import get_password_hash

# Path to the JSON database file
DB_FILE = Path("users.json")
# In-memory cache of the database
fake_users_db: Dict[str, Dict] = {}


def load_users_from_db() -> None:
    """Load user data from the JSON file into the in-memory cache."""
    if DB_FILE.exists():
        with open(DB_FILE, "r") as f:
            fake_users_db.update(json.load(f))
    else:
        # Create a default admin user if the database file doesn't exist
        import secrets

        admin_password = secrets.token_urlsafe(16)
        admin_user = {
            "username": "admin",
            "hashed_password": get_password_hash(admin_password),
        }
        fake_users_db["admin"] = admin_user
        save_users_to_db()
        print(f"Created default admin user with password: {admin_password}")


def save_users_to_db() -> None:
    """Save the current user data from the in-memory cache to the JSON file."""
    with open(DB_FILE, "w") as f:
        json.dump(fake_users_db, f, indent=4)


def get_user(username: str) -> Optional[Dict]:
    """Retrieve a user from the in-memory cache."""
    return fake_users_db.get(username)


# Load users when the application starts
load_users_from_db()