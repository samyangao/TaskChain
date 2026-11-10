# Privacy Note (P5)

**System:** TaskChain
**Law:** Republic Act No. 10173, Data Privacy Act of 2012

## What is collected and why

| Data | Classification | Why it is needed |
|---|---|---|
| ID Number | Personal information | Primary key of the registration profile; distinguishes two people with the same name. |
| First name, middle name, family name, name extension | Personal information | Identifies the account holder on requests, handovers and verification records. |
| Birthdate | Personal information | Confirms the account holder is at least 18; supports identity checks. Age is calculated, never trusted from the browser. |
| Purok / Street, Barangay, Municipality / City, Province, Country, ZIP Code | Personal information | Contact and jurisdiction for task coordination. |
| Email address | Personal information | Account identifier, OTP delivery and security alerts. |
| Username | Personal information | Login identifier that is easier to say during a demo than an email address. |
| Password | Sensitive personal information (credential) | Authentication. Stored only as a bcrypt hash, never readable. |
| Three security answers | Sensitive personal information (credential) | Account recovery when the password is forgotten. Stored only as bcrypt hashes, lowercased first. |
| Contact Number | Personal information | Lets a coordinator reach the account holder about an active task. **Encrypted at rest with AES-256.** |
| Office / Unit | Personal information (employment context) | Routes the task to the right team and controls which queue the user sees. |
| Date of Appointment | Personal information (employment context) | Establishes account history and eligibility. |
| Position / Designation | Personal information (employment context) | Shows the role of the person in the handover chain. |
| Privacy consent timestamp | Personal information | Evidence that consent was given, as required by RA 10173. |
| Activity log (event, username typed, IP, browser, time) | Personal information (traffic data) | Security monitoring, incident investigation and accountability. |

## What is not collected

No government ID numbers, no financial account numbers, no health records, no biometrics, and no data about minors (registration is refused under 18). The system does not use tracking cookies or third-party analytics.

## How it is protected

- Passwords, security answers and OTPs are bcrypt hashes.
- Contact Number is AES-256 ciphertext; only the owner can decrypt it through `/api/me`.
- All forms carry a per-session CSRF token and a server-verified CAPTCHA.
- Every SQL query is parameterized.
- The activity log is append-only; PostgreSQL rejects UPDATE and DELETE.
- The security dashboard is administrator-only and read-only.
- Secrets live in `.env` outside the served `frontend/` root and are gitignored.
- Errors are logged to `logs/error.log` outside the web root; users see a generic message.

## How long it is kept

Account and task records are kept for the school term and for the retention period required by the institution's records policy. Security logs are kept for the period needed for monitoring and audit. When data is no longer needed, the administrator deactivates the account and archives the record according to the institution's disposal procedure.

## Who can see it

The account holder sees their own profile. Coordinators and administrators see the fields needed to route and verify a task. The administrator sees the security dashboard. No other requester can open another requester's task or uploaded evidence.

## Rights of the data subject

Under RA 10173 the account holder has the right to be informed, to object, to access, to rectify, to erase or block, to damages, and to data portability. Requests go to the TaskChain administrator through the user's Office/Unit. The system supports correction through the administrator and deletion through account deactivation.

## Consent

Registration shows a required, unchecked checkbox: "I have read the Privacy Notice and agree to the collection and processing of my personal data in accordance with the Data Privacy Act of 2012 (RA 10173)." Registration is refused if it is not ticked, and the date and time of consent are stored in `security_profiles.privacy_consent_at`.

## Contact

TaskChain Administrator
Caraga State University — BS Information Technology
IT 107, 1st Semester A.Y. 2026–2027
