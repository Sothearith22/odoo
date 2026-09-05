from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUniversityPayment(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Student = self.env["university.student"]
        self.Fee = self.env["university.fee"]
        self.Payment = self.env["university.payment"]

        self.student = self.Student.create({"name": "Student A"})
        self.other_student = self.Student.create({"name": "Student B"})
        self.fee = self.Fee.create(
            {
                "student_id": self.student.id,
                "line_ids": [(0, 0, {"name": "Tuition", "amount": 100.0})],
            }
        )
        self.fee.action_post()

    def test_payment_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.Payment.create(
                {
                    "student_id": self.student.id,
                    "fee_id": self.fee.id,
                    "amount": 0.0,
                }
            )

    def test_payment_fee_must_match_student(self):
        with self.assertRaises(ValidationError):
            self.Payment.create(
                {
                    "student_id": self.other_student.id,
                    "fee_id": self.fee.id,
                    "amount": 25.0,
                }
            )

    def test_posted_payment_is_read_only(self):
        payment = self.Payment.create(
            {
                "student_id": self.student.id,
                "fee_id": self.fee.id,
                "amount": 25.0,
            }
        )

        payment.action_post()

        with self.assertRaises(ValidationError):
            payment.write({"reference": "CHANGED"})

        with self.assertRaises(ValidationError):
            payment.write({"state": "canceled"})