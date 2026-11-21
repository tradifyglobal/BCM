"""Immediate delivery for queued emails.

Frappe's scheduler flushes the Email Queue once per minute, so outgoing mail
normally waits up to sixty seconds. This hook enqueues a short-queue job as
soon as an Email Queue entry is committed, so delivery starts within seconds.
The scheduled flush remains as a safety net for retries and missed jobs.
"""

import frappe


def dispatch_immediately(doc, method=None):
    """after_insert hook on Email Queue: send as soon as the transaction commits."""
    if doc.send_after or frappe.are_emails_muted():
        return
    frappe.enqueue(
        "continuity360.email_dispatch.deliver",
        queue="short",
        enqueue_after_commit=True,
        job_id=f"c360_send_{doc.name}",
        deduplicate=True,
        email_queue_name=doc.name,
    )


def deliver(email_queue_name):
    doc = frappe.get_doc("Email Queue", email_queue_name)
    # send() re-checks status under lock, so a concurrent scheduler flush is safe.
    if doc.status == "Not Sent":
        doc.send()
