# System Proposal — Appendix A

**System name:** TaskChain

**Who uses it:** Requesters who file a service request; coordinators who review and assign it; personnel who accept, process and hand it over; verifiers who approve or reject completion; and an administrator who manages accounts and monitors security.

**What it stores:** Account identity and contact data; service requests and their status history; assignment, handover and custody records; evidence files; comments and notifications; and an append-only security activity log.

**Why accounts need protecting:** TaskChain carries personal contact data and operational records about who handled each request and when. A compromised account could read another office's records, tamper with a handover, or approve work that was never done. The custody chain and audit trail are only trustworthy if the identity behind each action is verified.

**Sensitive field to encrypt (protection 13):** Contact Number — `security_profiles.contact_number_enc`, encrypted with pgcrypto AES-256 (`pgp_sym_encrypt`) and decrypted only for the owner through `/api/me`.

## System fields (four fields, three kinds)

| Field name | Kind | Required? | Rule | Error message |
|---|---|---|---|---|
| Office / Unit | Dropdown | Required | One of Registrar, Finance, IT, HR, Admin. Server checks the value against the list. | Please select a valid Office/Unit. |
| Contact Number | Formatted number | Required | Exactly 11 digits, starts with 09. Encrypted at rest with AES-256. | Contact number must be 11 digits and start with 09. |
| Date of Appointment | Date | Required | A real date; it cannot be in the future. | Date of Appointment cannot be in the future. |
| Position / Designation | Free text | Required | Letters and spaces only; 2–50 characters; no double spaces. | Position / Designation may contain letters and spaces only. |

## Core registration identity

`security_profiles.id_number` is the primary key of the registration profile and follows `xxxx-xxxx` (placeholder `xxxx-xxxx`). The TaskChain `users` table keeps its UUID primary key because tasks, handovers, evidence and audit rows reference it; the two rows are joined 1:1 on `user_id`. This preserves the handout's "ID Number is the primary key" rule for the registration record without breaking the existing workflow.

---

Instructor's decision: ☐ Approved   ☐ Revise and resubmit

Signature and date: ______________________________
