# Error Message Mapping (P6)

Every message below is produced by `app/services/registration_rules.py` or the route that owns the rule. The browser mirrors the same wording; the server is the authority.

## Core fields

| Field | Rule | Exact message |
|---|---|---|
| ID Number | Required / format `xxxx-xxxx` | ID Number must follow the format xxxx-xxxx. |
| ID Number | Already exists | This ID Number is already registered. |
| First Name | Required | First Name is required. |
| First Name | At least 2 characters | First Name must be at least 2 characters. |
| First Name | At most 23 characters | First Name must be at most 23 characters. |
| First Name | Letters only | Numbers are not allowed in First Name. |
| First Name | No special characters | Special characters are not allowed in First Name. |
| First Name | No double spaces | Double space is not allowed. |
| First Name | Not all capitals | Do not use all capital letters. |
| First Name | No three identical letters in a row | Three consecutive identical letters are not allowed. |
| First Name | First letter capital | First letter of your name must be capital. |
| First Name | Title Case | Only the first letter of each word should be capital. |
| Middle Name | Same rules, only if filled | (same messages, with "Middle Name") |
| Family Name | Required + same rules | (same messages, with "Family Name") |
| Name Extension | Jr., Sr., I, II, III, IV, IX, X | Select a valid Name Extension. |
| Birthdate | Required | Birthdate is required. |
| Birthdate | Real date | Enter a valid birthdate. |
| Birthdate | Not in the future | Birthdate cannot be in the future. |
| Birthdate | At least 18 years old | You must be at least 18 years old to register. |
| Purok / Street | Required | Purok / Street is required. |
| Purok / Street | 3–50 characters | Purok / Street must be 3-50 characters. |
| Purok / Street | Letters, digits, spaces only | Purok / Street may contain letters, digits and spaces only. |
| Purok / Street | No double spaces | Double space is not allowed. |
| Barangay | Required | Barangay is required. |
| Barangay | 2–50 characters | Barangay must be 2-50 characters. |
| Barangay | Letters and spaces only | Barangay may contain letters and spaces only. |
| Barangay | Title Case | Barangay must be in Title Case. |
| Municipality / City | Same as Barangay | (same messages, with "Municipality / City") |
| Province | Same as Barangay | (same messages, with "Province") |
| Country | Same as Barangay | (same messages, with "Country") |
| ZIP Code | Exactly 4 digits | ZIP Code must be exactly 4 digits. |
| Email | Required | Email is required. |
| Email | At most 100 characters | Email must be at most 100 characters. |
| Email | Valid format, no spaces | Please enter a valid email address. |
| Email | Unique | This email is already registered. |
| Username | Required | Username is required. |
| Username | Starts with a letter; letters and digits only | Username must start with a letter and contain only letters and digits. |
| Username | At least 6 characters | Username must be at least 6 characters. |
| Username | At most 19 characters | Username must be at most 19 characters. |
| Username | Unique | This username is already taken. |
| Password | Required | Password is required. |
| Password | At least 11 characters | Password must be at least 11 characters. |
| Password | At most 64 characters | Password must be at most 64 characters. |
| Password | Weak cannot be submitted | Password is too weak. Use uppercase, lowercase, numbers or symbols. |
| Re-enter Password | Must match | Passwords do not match. |
| Security answer | Required | Each security answer is required. |
| Security answer | 2–50 characters | Answer must be 2-50 characters. |
| Security answer | Letters and spaces only | Answer may contain letters and spaces only. |
| Security answer | No double spaces | Double space is not allowed. |
| Security answer | Re-enter must match | Answers do not match. |
| Privacy consent | Required | You must agree to the Privacy Notice to register. |
| CAPTCHA | Server check | The CAPTCHA code is not correct. Please try again. |
| Honeypot | Hidden field filled | (silent success, no account created) |

## System fields

| Field | Rule | Exact message |
|---|---|---|
| Office / Unit | Allowed dropdown values only | Please select a valid Office/Unit. |
| Contact Number | 11 digits, starts with 09 | Contact number must be 11 digits and start with 09. |
| Date of Appointment | Required | Date of Appointment is required. |
| Date of Appointment | Real date | Enter a valid Date of Appointment. |
| Date of Appointment | Not in the future | Date of Appointment cannot be in the future. |
| Position / Designation | Required | Position / Designation is required. |
| Position / Designation | 2–50 characters | Position / Designation must be 2-50 characters. |
| Position / Designation | Letters and spaces only | Position / Designation may contain letters and spaces only. |
| Position / Designation | No double spaces | Double space is not allowed. |

## Authentication and recovery

| Field / event | Rule | Exact message |
|---|---|---|
| Login | Wrong username or password (identical) | Invalid username or password. |
| Login | Locked account / IP | Too many failed attempts. Please wait before trying again. |
| Login CAPTCHA | Wrong | The CAPTCHA code is not correct. Please try again. |
| Login OTP | Wrong | That code is not correct. N attempts left. |
| OTP | Expired | That code has expired. Request a new one. |
| OTP | Three wrong entries | Too many incorrect codes. Request a new one. |
| OTP | No active code | No active code was found. Request a new one. |
| OTP | Format | Enter the 6-digit code from your email. |
| Registration | Mail could not be sent | We could not send the verification email. Please try again or contact the administrator. |
| Forgot Password | Wrong answer (identical for unknown user) | That answer is not correct. |
| Forgot Password | Answer mismatch | Answers do not match. |
| Reset | Password mismatch | Mismatch Password. |
| Reset | Reused password | You cannot reuse a recent password. |
| Reset | Used/expired token | This password reset link is invalid or has already been used. |
| Reset | Success | Successfully Change Password. |
| Account security | Current password wrong | Your current password is not correct. |
| Account security | Reused password | You cannot reuse a recent password. |
| Account security | Success | Successfully Change Password. |
