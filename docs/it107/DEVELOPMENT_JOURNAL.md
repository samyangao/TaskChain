# Development Journal (Appendix C)

One page per week. Write it in your own words; it is read for honesty, not polish. The entries below are a template based on the work already done — replace the wording with your own experience and add dates and commit counts.

---

## Week 1 — dates: ____________

**What I built this week**
Read the IT 107 handout, computed the seed from student number 241-01803 (D1 = 0, D2 = 3), and wrote the System Proposal for TaskChain. Checked the existing Flask/PostgreSQL project and listed what was missing against the handout.

**Where I got stuck**
The handout says ID Number is the primary key, but TaskChain already uses a UUID primary key because tasks, handovers and audit rows reference it. Changing the primary key would have broken every foreign key.

**How I solved it**
I created `security_profiles` with `id_number` as its primary key and a 1:1 `user_id` link to `users`. The registration identity keeps the handout's rule, and the existing workflow keeps working.

**What I learned about security**
A primary key chosen early is hard to change later; plan identity before building dependent tables.

**Commits this week:** ____

---

## Week 2 — dates: ____________

**What I built this week**
Added migration `002`, the registration validation service, the privacy notice and consent timestamp, the pure-Python PNG CAPTCHA, and the honeypot. Built the registration page with per-field errors, live username availability, password strength meter and the three seeded questions.

**Where I got stuck**
The server and browser both validate the same fields. It was easy for the two rule sets to drift, so a field could pass the browser and fail the server (or the reverse).

**How I solved it**
The browser mirrors the server's wording, but the server re-runs every rule in `registration_rules.py`. I tested by turning JavaScript off and submitting bad input; the server still rejected it.

**What I learned about security**
Client-side validation is for the user, not for the attacker. The server must be able to reject every request on its own.

**Commits this week:** ____

---

## Week 3 — dates: ____________

**What I built this week**
Email OTP (register, login, reset) with bcrypt hashes, 3-minute expiry, 3 attempts, 60-second resend cooldown and 3 resends per 15 minutes. Two-step login, the seeded 3-tier lockout (15/30/60 seconds), IP blocking, alert emails, Forgot Password and the one-time reset token.

**Where I got stuck**
At first the lockout re-locked on every failure after the third, so the counter could never reach six and tier 2 was unreachable. I also had to make sure a wrong CAPTCHA did not lock the account.

**How I solved it**
`lockout_for()` now returns a lock only when the counter crosses 3, 6 or 9 (and every third failure after 9). A wrong CAPTCHA feeds the IP threshold but not the account counter.

**What I learned about security**
Lockout is a balance: it must stop guessing without letting one typo deny a real user, and it must live on the server so clearing cookies does not reset it.

**Commits this week:** ____

---

## Week 4 — dates: ____________

**What I built this week**
The append-only activity log, the admin-only monitoring dashboard (cards, 24-hour chart, top IPs, flags, filters, 60-second refresh) and `scripts/monitor.py`. Added CSRF, security headers, the idle timeout, password history, the file logger and the documentation set.

**Where I got stuck**
The dashboard must show attacker-controlled text without running it, and the log must be impossible to edit from the UI.

**How I solved it**
Every dynamic value goes through `esc()`. The log is append-only at the PostgreSQL level (a trigger rejects UPDATE/DELETE), and the dashboard has no edit or delete controls.

**What I learned about security**
Monitoring is only useful if the log itself is trustworthy. A read-only dashboard and an append-only table are part of the defence, not just reporting.

**Commits this week:** ____
