"""Two-site private-file and real background-worker isolation checks."""

import os
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import requests

from restore_drill_site import BENCH


def site_name(token, label):
    return f"c360-tenant-{token}-{label}.localhost"


@contextmanager
def connected(site):
    import frappe

    frappe.init(site)
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        yield
    finally:
        frappe.destroy()


def setup(token):
    import frappe
    databases = set()
    for label in ("a", "b"):
        site = site_name(token, label)
        with connected(site):
            if frappe.conf.db_name in databases:
                raise RuntimeError("The disposable sites share a database.")
            databases.add(frappe.conf.db_name)
            company = frappe.get_doc({
                "doctype": "C360 Company", "company_name": f"tenant-{label}-{token}",
            }).insert()
            files = [
                (True, f"shared-{token}.txt", f"private-{label}-{token}"),
                (False, f"shared-{token}.txt", f"public-{label}-{token}"),
            ]
            if label == "a":
                files.extend([
                    (True, f"only-a-{token}.txt", f"private-only-a-{token}"),
                    (False, f"only-a-{token}.txt", f"public-only-a-{token}"),
                ])
            for is_private, filename, content in files:
                frappe.get_doc({
                    "doctype": "File", "file_name": filename, "is_private": int(is_private),
                    "content": content, "attached_to_doctype": "C360 Company",
                    "attached_to_name": company.name,
                }).insert()
            frappe.db.commit()


def request(session, site, path, *, method="GET", **kwargs):
    return session.request(
        method, f"http://backend:8000{path}",
        headers={"X-Frappe-Site-Name": site}, timeout=15, **kwargs,
    )


def require_status(response, expected, description):
    if response.status_code not in expected:
        raise RuntimeError(f"{description}: unexpected HTTP status {response.status_code}.")


def wait_for_backend(site):
    deadline = time.monotonic() + 90
    last_status = "not reachable"
    with requests.Session() as session:
        while time.monotonic() < deadline:
            try:
                response = request(session, site, "/api/method/ping")
                if response.status_code == 200 and response.json().get("message") == "pong":
                    return
                last_status = f"HTTP {response.status_code}"
            except (requests.ConnectionError, requests.Timeout) as error:
                last_status = type(error).__name__
            time.sleep(1)
    raise RuntimeError(f"Disposable backend did not become ready: {last_status}.")


def verify_files(token, passwords):
    sessions = {}
    try:
        for label in ("a", "b"):
            site = site_name(token, label)
            session = requests.Session()
            sessions[label] = session
            response = request(session, site, "/api/method/login", method="POST", data={
                "usr": "Administrator", "pwd": passwords[label],
            })
            require_status(response, (200,), f"Site {label} login")
            if session.cookies.get("sid") in (None, "Guest"):
                raise RuntimeError(f"Site {label} did not create an authenticated session.")
            response = request(session, site, f"/private/files/shared-{token}.txt")
            require_status(response, (200,), f"Site {label} private file")
            if response.content != f"private-{label}-{token}".encode():
                raise RuntimeError(f"Site {label} returned the wrong private file content.")

        with requests.Session() as guest:
            require_status(
                request(guest, site_name(token, "a"), f"/private/files/shared-{token}.txt"),
                (401, 403), "Guest private-file access",
            )
        for source, target in (("a", "b"), ("b", "a")):
            with requests.Session() as cross_site:
                cross_site.cookies.update(sessions[source].cookies)
                require_status(
                    request(cross_site, site_name(token, target), f"/private/files/shared-{token}.txt"),
                    (401, 403), f"Site {source} session on site {target}",
                )
        require_status(
            request(sessions["b"], site_name(token, "b"), f"/private/files/only-a-{token}.txt"),
            (401, 403, 404), "Site B access to an A-only file",
        )
    finally:
        for session in sessions.values():
            session.close()


def gateway_request(session, host, path, *, method="GET", headers=None, **kwargs):
    request_headers = {"Host": host}
    request_headers.update(headers or {})
    return session.request(
        method, f"http://drill-gateway:8080{path}", headers=request_headers, timeout=15, **kwargs,
    )


def verify_gateway(token, passwords):
    sites = {label: site_name(token, label) for label in ("a", "b")}
    sessions = {}
    deadline = time.monotonic() + 90
    last_issue = "not reachable"
    with requests.Session() as probe:
        while time.monotonic() < deadline:
            try:
                response = gateway_request(probe, sites["a"], "/api/method/ping")
                if response.status_code == 200 and response.json().get("message") == "pong":
                    break
                last_issue = f"HTTP {response.status_code}"
            except (requests.ConnectionError, requests.Timeout) as error:
                last_issue = type(error).__name__
            time.sleep(1)
        else:
            raise RuntimeError(f"Disposable gateway did not become ready: {last_issue}.")

        require_status(
            gateway_request(probe, "unknown.example.invalid", f"/files/shared-{token}.txt",
                            headers={"X-Frappe-Site-Name": sites["a"], "X-Forwarded-Host": sites["a"]}),
            (404,), "Unknown tenant host",
        )
        require_status(
            gateway_request(probe, sites["a"], f"/protected/private/files/shared-{token}.txt"),
            (404,), "Direct protected-file access",
        )
        require_status(
            gateway_request(probe, sites["b"], f"/files/only-a-{token}.txt"),
            (404,), "Site B access to an A-only public file",
        )

    try:
        for label in ("a", "b"):
            other = "b" if label == "a" else "a"
            with requests.Session() as wrong_credentials:
                require_status(
                    gateway_request(
                        wrong_credentials, sites[label], "/api/method/login", method="POST",
                        data={"usr": "Administrator", "pwd": passwords[other]},
                    ),
                    (401, 403), f"Gateway site {label} rejected the other site's credentials",
                )
            session = requests.Session()
            sessions[label] = session
            public = gateway_request(session, sites[label], f"/files/shared-{token}.txt")
            require_status(public, (200,), f"Site {label} public file")
            if public.content != f"public-{label}-{token}".encode():
                raise RuntimeError(f"Site {label} returned the wrong public file content.")
            require_status(
                gateway_request(session, sites[label], f"/private/files/shared-{token}.txt"),
                (401, 403), f"Site {label} guest private-file access",
            )
            response = gateway_request(session, sites[label], "/api/method/login", method="POST", data={
                "usr": "Administrator", "pwd": passwords[label],
            })
            require_status(response, (200,), f"Gateway site {label} login")
            if session.cookies.get("sid") in (None, "Guest"):
                raise RuntimeError(f"Gateway site {label} did not create an authenticated session.")
            private = gateway_request(session, sites[label], f"/private/files/shared-{token}.txt")
            require_status(private, (200,), f"Gateway site {label} private file")
            if private.content != f"private-{label}-{token}".encode():
                raise RuntimeError(f"Gateway site {label} returned the wrong private file content.")

        spoofed = gateway_request(
            sessions["a"], sites["a"], f"/private/files/shared-{token}.txt",
            headers={"X-Frappe-Site-Name": sites["b"], "X-Forwarded-Host": sites["b"]},
        )
        require_status(spoofed, (200,), "Spoofed tenant headers")
        if spoofed.content != f"private-a-{token}".encode():
            raise RuntimeError("Spoofed headers selected another tenant.")

        for source, target in (("a", "b"), ("b", "a")):
            with requests.Session() as cross_site:
                cross_site.cookies.set("sid", sessions[source].cookies.get("sid"))
                require_status(
                    gateway_request(cross_site, sites[target], f"/private/files/shared-{token}.txt"),
                    (401, 403), f"Gateway site {source} session on site {target}",
                )
    finally:
        for session in sessions.values():
            session.close()


def company_name(site):
    import frappe

    with connected(site):
        names = frappe.get_all("C360 Company", pluck="name")
        if len(names) != 1:
            raise RuntimeError("Each disposable site must contain exactly one company.")
        return names[0], frappe.db.get_value("C360 Company", names[0], "company_name")


def verify_jobs(token):
    import frappe

    sites = {label: site_name(token, label) for label in ("a", "b")}
    companies = {label: company_name(site)[0] for label, site in sites.items()}
    if companies["a"] != companies["b"]:
        raise RuntimeError("Expected identical document IDs for the isolation test.")
    for label, other in (("a", "b"), ("b", "a")):
        expected_other = f"job-a-{token}" if other == "a" else f"tenant-b-{token}"
        with connected(sites[label]):
            job = frappe.enqueue(
                "frappe.client.set_value", queue="short", doctype="C360 Company",
                name=companies[label], fieldname="company_name", value=f"job-{label}-{token}",
            )
            if job is None:
                raise RuntimeError(f"Site {label} job was not enqueued.")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if company_name(sites[label])[1] == f"job-{label}-{token}":
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"Site {label} background job did not complete.")
        if company_name(sites[other])[1] != expected_other:
            raise RuntimeError(f"Site {label} job changed site {other}'s company.")


def main(stage, token):
    import pwd

    if stage not in ("setup", "verify") or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("A valid drill stage and generated token are required.")
    if os.getuid() != 0:
        raise RuntimeError("The disposable setup container must start as root.")
    passwords = {
        label: Path(f"/run/secrets/tenant_{label}_password").read_text()
        for label in ("a", "b")
    }
    if not all(passwords.values()) or passwords["a"] == passwords["b"]:
        raise RuntimeError("Distinct nonempty disposable tenant credentials are required.")
    account = pwd.getpwnam("frappe")
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ["HOME"] = account.pw_dir
    os.chdir(BENCH / "sites")
    if stage == "setup":
        setup(token)
    else:
        wait_for_backend(site_name(token, "a"))
        verify_files(token, passwords)
        verify_gateway(token, passwords)
        verify_jobs(token)
        print("PASS: internal gateway routing, public/private files, sessions and background jobs")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
