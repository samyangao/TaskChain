# Seed Table

**Student number:** 241-01803
**D2 = last digit = 3**
**D1 = second-to-last digit = 0**

| Parameter | Formula | Calculation | My value |
|---|---|---|---|
| Min username length | 6 + (D1 mod 3) | 6 + (0 mod 3) | **6** |
| Max username length | 16 + (D2 mod 5) | 16 + (3 mod 5) | **19** |
| Min password length | 8 + (D2 mod 4) | 8 + (3 mod 4) | **11** |
| Max length of each name field | 20 + D2 | 20 + 3 | **23** |
| Failed log-ins before "Forgot Password?" appears | 2 + (D1 mod 2) | 2 + (0 mod 2) | **2** |
| Lockout tier 1 (seconds) | 15 + D1 | 15 + 0 | **15** |
| Lockout tier 2 (seconds) | 30 + (2 × D1) | 30 + 0 | **30** |
| Lockout tier 3 (seconds) | 60 + (4 × D1) | 60 + 0 | **60** |
| OTP expiry (minutes) | 3 + (D2 mod 3) | 3 + (3 mod 3) | **3** |
| Idle session timeout (minutes) | 5 + (D1 mod 5) | 5 + (0 mod 5) | **5** |
| IP block threshold (failures in 10 min) | 8 + D2 | 8 + 3 | **11** |
| Auth question A | Q[(D2 mod 8) + 1] | Q[(3 mod 8) + 1] | **Q4** |
| Auth question B | Q[((D2 + 3) mod 8) + 1] | Q[6 + 1] | **Q7** |
| Auth question C | Q[((D2 + 5) mod 8) + 1] | Q[(0) + 1] | **Q1** |

## Questions

- **Q4:** What is your mother's maiden first name?
- **Q7:** What was the name of your elementary school?
- **Q1:** What was the name of your first pet?

## Where these values live

All of them are derived once in `app/config.py` (`SEED_D1`, `SEED_D2`, `MIN_USERNAME_LENGTH`, `LOCKOUT_TIERS`, `OTP_EXPIRY_MINUTES`, `IDLE_TIMEOUT_MINUTES`, `IP_BLOCK_THRESHOLD`, `AUTH_QUESTION_NUMBERS`). No route or template hardcodes a different value.
