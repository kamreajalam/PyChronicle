"""Authentication service — credential checks, lockout, session issuing.

Produces the security-flavoured trace data (login / logout, failed auth,
lockouts, token issue and refresh) with realistic accounts, IP addresses,
user agents and devices held in the traced variables.
"""

import hashlib
import os
import random

ACCOUNTS = [
    ("p.venkataraman@kaveryfreight.in", "operations", "IN", "Asia/Kolkata"),
    ("j.okonkwo@meridian-logistics.nl", "warehouse-lead", "NL", "Europe/Amsterdam"),
    ("s.halberstadt@halberstadt-werke.de", "finance", "DE", "Europe/Berlin"),
    ("e.fielding@trentfielding.co.uk", "admin", "GB", "Europe/London"),
    ("m.tanaka@straitscold.com.sg", "analyst", "SG", "Asia/Singapore"),
    ("r.delacruz@riograndedist.com", "dispatcher", "US", "America/Chicago"),
    ("a.almansoori@gulfmarine.ae", "procurement", "AE", "Asia/Dubai"),
    ("l.moreau@pacificcrest.com", "support", "US", "America/Los_Angeles"),
]

CLIENTS = [
    ("Chrome 141", "Windows 11", "desktop"),
    ("Safari 18.2", "macOS 15.3", "desktop"),
    ("Edge 140", "Windows 10", "desktop"),
    ("Firefox 137", "Ubuntu 24.04", "desktop"),
    ("Chrome Mobile 141", "Android 15", "mobile"),
    ("Safari Mobile 18", "iOS 18.3", "mobile"),
    ("PyChronicle-Agent/1.4", "Debian 12", "service"),
]

SUBNETS = ["10.42", "172.19", "192.168", "203.0", "198.51"]

LOCKOUT_THRESHOLD = 3


def hash_password(password, salt):
    """Salted SHA-256, matching how credentials are stored at rest."""
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return digest


def client_ip(rng):
    """Builds a plausible source address for the request."""
    prefix = rng.choice(SUBNETS)
    return f"{prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"


def verify_credentials(email, supplied_password, stored_hash, salt):
    """Constant-shape credential check; raises on unknown account."""
    if "@" not in email:
        raise ValueError(f"malformed principal: {email!r}")
    candidate = hash_password(supplied_password, salt)
    matched = candidate == stored_hash
    return matched


def issue_session(email, role, ip_address, client, rng):
    """Creates the session record returned to a successful caller."""
    browser, operating_system, device = client
    token_seed = f"{email}|{ip_address}|{rng.random()}"
    access_token = hashlib.sha256(token_seed.encode("utf-8")).hexdigest()[:40]
    refresh_token = hashlib.sha256(("r:" + token_seed).encode("utf-8")).hexdigest()[:40]
    return {
        "principal": email,
        "role": role,
        "ip_address": ip_address,
        "browser": browser,
        "operating_system": operating_system,
        "device": device,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "ttl_seconds": 3600,
    }


def record_failure(failure_counts, email):
    """Tracks consecutive failures and reports whether to lock the account."""
    failure_counts[email] = failure_counts.get(email, 0) + 1
    locked = failure_counts[email] >= LOCKOUT_THRESHOLD
    return locked


def authenticate(account, supplied_password, failure_counts, rng):
    """One end-to-end authentication attempt."""
    email, role, country, timezone = account
    salt = email.split("@")[1]
    stored_hash = hash_password("correct-horse-battery", salt)

    ip_address = client_ip(rng)
    client = rng.choice(CLIENTS)

    if failure_counts.get(email, 0) >= LOCKOUT_THRESHOLD:
        return {"outcome": "locked", "principal": email, "ip_address": ip_address}

    matched = verify_credentials(email, supplied_password, stored_hash, salt)
    if not matched:
        locked = record_failure(failure_counts, email)
        return {
            "outcome": "locked" if locked else "rejected",
            "principal": email,
            "ip_address": ip_address,
            "attempts": failure_counts[email],
        }

    failure_counts.pop(email, None)
    session = issue_session(email, role, ip_address, client, rng)
    session["outcome"] = "granted"
    session["country"] = country
    session["timezone"] = timezone
    return session


def refresh_session(session, rng):
    """Rotates an access token using the refresh token."""
    if session.get("outcome") != "granted":
        raise PermissionError("cannot refresh a session that was never granted")
    rotated = hashlib.sha256(
        (session["refresh_token"] + str(rng.random())).encode("utf-8")
    ).hexdigest()[:40]
    session["access_token"] = rotated
    session["ttl_seconds"] = 3600
    return session


def main():
    scale = int(os.environ.get("PYCHRONICLE_SCALE", "10"))
    seed = int(os.environ.get("PYCHRONICLE_SEED", "13"))
    rng = random.Random(seed)

    failure_counts = {}
    granted = 0
    rejected = 0
    locked = 0

    for attempt in range(scale):
        account = rng.choice(ACCOUNTS)
        # Roughly a third of attempts use a stale password.
        password = "correct-horse-battery" if rng.random() > 0.34 else "Winter2024!"

        result = authenticate(account, password, failure_counts, rng)
        outcome = result["outcome"]

        if outcome == "granted":
            granted += 1
            if attempt % 4 == 0:
                refresh_session(result, rng)
        elif outcome == "locked":
            locked += 1
        else:
            rejected += 1

    print(f"attempts={scale} granted={granted} rejected={rejected} locked={locked}")
    print(f"accounts_with_failures={sorted(failure_counts)}")
    return {"granted": granted, "rejected": rejected, "locked": locked}


if __name__ == "__main__":
    main()
