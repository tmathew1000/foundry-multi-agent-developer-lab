import unittest

from travel_buddy.verification import MODULE_IDENTIFIERS, normalize_module_identifier


class VerificationTests(unittest.TestCase):
    def test_all_expands_to_modules_zero_through_five(self) -> None:
        self.assertEqual(MODULE_IDENTIFIERS, normalize_module_identifier("all"))

    def test_invalid_module_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "0-5 or all"):
            normalize_module_identifier("6")


if __name__ == "__main__":
    unittest.main()
