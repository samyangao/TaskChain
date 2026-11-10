"""Server-side rule tests. Run: python -m unittest discover -s tests -v"""

import unittest

from app.config import (
    AUTH_QUESTION_NUMBERS,
    IDLE_TIMEOUT_MINUTES,
    IP_BLOCK_THRESHOLD,
    LOCKOUT_TIERS,
    MAX_NAME_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH,
    OTP_EXPIRY_MINUTES,
)
from app.services.registration_rules import (
    validate_answer,
    validate_birthdate,
    validate_id_number,
    validate_name,
    validate_password,
    validate_username,
)


class SeedTests(unittest.TestCase):
    def test_seed_values(self):
        self.assertEqual(MIN_USERNAME_LENGTH, 6)
        self.assertEqual(MAX_USERNAME_LENGTH, 19)
        self.assertEqual(MIN_PASSWORD_LENGTH, 11)
        self.assertEqual(MAX_NAME_LENGTH, 23)
        self.assertEqual(LOCKOUT_TIERS, ((3, 15), (6, 30), (9, 60)))
        self.assertEqual(OTP_EXPIRY_MINUTES, 3)
        self.assertEqual(IDLE_TIMEOUT_MINUTES, 5)
        self.assertEqual(IP_BLOCK_THRESHOLD, 11)
        self.assertEqual(AUTH_QUESTION_NUMBERS, (4, 7, 1))


class NameTests(unittest.TestCase):
    def test_lowercase_first_letter(self):
        self.assertEqual(validate_name("juan", "First Name"), "First letter of your name must be capital.")

    def test_all_caps(self):
        self.assertEqual(validate_name("JUAN", "First Name"), "Do not use all capital letters.")

    def test_digit(self):
        self.assertEqual(validate_name("Ju4n", "First Name"), "Numbers are not allowed in First Name.")

    def test_special(self):
        self.assertEqual(validate_name("Juan!", "First Name"), "Special characters are not allowed in First Name.")

    def test_double_space(self):
        self.assertEqual(validate_name("Juan  Carlo", "First Name"), "Double space is not allowed.")

    def test_triple_letter(self):
        self.assertEqual(validate_name("Juaaan", "First Name"), "Three consecutive identical letters are not allowed.")

    def test_title_case(self):
        self.assertIsNone(validate_name("Juan Carlo", "First Name"))

    def test_optional_middle_name(self):
        self.assertIsNone(validate_name("", "Middle Name", required=False))


class FieldTests(unittest.TestCase):
    def test_id_format(self):
        self.assertEqual(validate_id_number("1234-567"), "ID Number must follow the format xxxx-xxxx.")
        self.assertIsNone(validate_id_number("2024-0147"))

    def test_under_18(self):
        from datetime import date
        born = date.today().replace(year=date.today().year - 17)
        self.assertEqual(validate_birthdate(born.isoformat())[0],
                         "You must be at least 18 years old to register.")

    def test_future_birthdate(self):
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(validate_birthdate(future)[0], "Birthdate cannot be in the future.")

    def test_username(self):
        self.assertEqual(validate_username("1abcde"),
                         "Username must start with a letter and contain only letters and digits.")
        self.assertEqual(validate_username("abc"),
                         "Username must be at least 6 characters.")
        self.assertEqual(validate_username("a" * 20),
                         "Username must be at most 19 characters.")
        self.assertIsNone(validate_username("juan24"))

    def test_password_weak(self):
        self.assertEqual(validate_password("abcdefghijk", "abcdefghijk"),
                         "Password is too weak. Use uppercase, lowercase, numbers or symbols.")

    def test_password_mismatch(self):
        self.assertEqual(validate_password("StrongPass1!", "StrongPass2!"), "Passwords do not match.")

    def test_answer(self):
        self.assertEqual(validate_answer("B4ntay"), "Answer may contain letters and spaces only.")
        self.assertEqual(validate_answer("  "), "Each security answer is required.")
        self.assertIsNone(validate_answer("San Jose Elementary"))


if __name__ == "__main__":
    unittest.main()
