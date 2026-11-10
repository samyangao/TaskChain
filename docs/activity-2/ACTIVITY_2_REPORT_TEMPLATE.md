# IT107 Activity 2 — Authentication & Rate-Limiting Laboratory Analysis

## 1. Environment Setup
- Platform: Windows
- Application: SecuritySys (Flask)
- Target: `http://127.0.0.1:5000/api/login` `http://127.0.0.1:5000/lab`
- Lab identifier: `admin12@example.com`
- Candidate list: 13 common passwords + `00000`–`05000` = 5,014 candidates.

## 2. Phase 2 — Unprotected Login Test
**Screenshot:** Insert your screenshot here.

Record:
- Total attempts: ______
- Elapsed time: ______ seconds
- Password discovered: ______
- HTTP status: ______

**Observation:** Describe how the tester continued accepting failed authentication requests until the valid candidate was reached.

## 3. Phase 3 — Protected Login Test
**Screenshot:** Insert your screenshot here.

Record:
- Attempts before block: ______
- Failed attempts: ______
- Elapsed time: ______ seconds
- Blocking HTTP status: ______

**Observation:** Describe how the temporary lockout/rate-limiting mechanism interrupted repeated authentication attempts.

## 4. Analysis and Reflection
### Rate limiting
Rate limiting restricts how frequently authentication requests can be made. This reduces the speed and volume of automated password guessing and makes large-scale guessing less practical.

### Account lockout
A temporary account lockout blocks further attempts after a defined number of consecutive failures. In this laboratory, the protected login uses five failed attempts followed by a temporary lockout.

### CAPTCHA
CAPTCHA can add another barrier against automated login activity by requiring an interaction that is difficult for simple automated scripts to perform. CAPTCHA is most effective as an additional control rather than the only authentication defense.

### Comparison
The unprotected test demonstrates that repeated automated requests can continue without an effective barrier. The protected test demonstrates that the server changes its response after repeated failures, causing the laboratory tester to receive an HTTP 429 response and stop.

## 5. Conclusion
The laboratory demonstrates why authentication systems should not rely only on password correctness. Rate limiting, temporary lockouts, and additional anti-automation controls help reduce brute-force and credential-guessing risk. The results also show that defensive controls change observable request behavior, which can be measured through HTTP responses, attempt counts, and elapsed time.
