import unittest
from datetime import date, timedelta

from continuity360.rules import (
    call_tree_span,
    call_tree_structure,
    crisis_closure,
    date_order,
    dependency_target,
    exercise_completion,
    incident_lifecycle,
    next_bcp_version,
    recovery_objectives,
    review_reminder_slot,
    risk_score,
)


class RiskTests(unittest.TestCase):
    def test_scoring_and_rating_boundaries(self):
        for likelihood, impact, score, rating in [
            (1, 5, 5, "Low"), (2, 3, 6, "Medium"),
            (3, 4, 12, "High"), (4, 5, 20, "Critical"), (5, 5, 25, "Critical"),
        ]:
            with self.subTest(likelihood=likelihood, impact=impact):
                self.assertEqual(risk_score(likelihood, impact), (score, rating))

    def test_invalid_risk_inputs_are_rejected(self):
        for value in (0, 6, -1, 2.5, None, "", "unknown", float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                risk_score(value, 3)


class RecoveryTests(unittest.TestCase):
    def test_bcp_minor_and_major_revisions(self):
        for previous, kind, expected in (
            ("1.0", "Minor", "1.1"), ("1.9", "Minor", "1.10"),
            ("1.10", "Major", "2.0"), ("2.0", "Minor", "2.1"),
        ):
            with self.subTest(previous=previous, kind=kind):
                self.assertEqual(next_bcp_version(previous, kind), expected)

    def test_bcp_invalid_version_or_revision_is_rejected(self):
        for previous, kind in (
            ("0.1", "Minor"), ("1", "Minor"), ("01.0", "Minor"), ("1.01", "Minor"),
            ("1.0", "Patch"), (None, "Major"), ("1.0\n", "Minor"),
        ):
            with self.subTest(previous=previous, kind=kind), self.assertRaises(ValueError):
                next_bcp_version(previous, kind)

    def test_valid_targets_allow_zero_data_loss(self):
        self.assertEqual(recovery_objectives(60, 0, 120), (60, 0, 120))

    def test_rpo_is_not_incorrectly_constrained_by_rto(self):
        self.assertEqual(recovery_objectives(15, 60, 120), (15, 60, 120))

    def test_mtpd_leaves_time_after_it_recovery(self):
        for rto, rpo, mtpd in [(120, 15, 120), (121, 15, 120), (0, 0, 0), (-1, 0, 60), (1, -1, 60)]:
            with self.subTest(rto=rto, rpo=rpo, mtpd=mtpd), self.assertRaises(ValueError):
                recovery_objectives(rto, rpo, mtpd)

    def test_non_finite_recovery_values_are_rejected(self):
        for value in (float("nan"), float("inf"), None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recovery_objectives(value, 0, 120)

    def test_treatment_due_date_cannot_precede_start(self):
        with self.assertRaises(ValueError):
            date_order(date(2026, 11, 15), date(2026, 11, 14), "Due date")
        date_order(date(2026, 11, 15), date(2026, 11, 15), "Due date")

    def test_review_reminder_windows_and_weekly_overdue_slots(self):
        today = date(2026, 1, 1)
        for days, expected in (
            (31, None), (30, "before-30"), (8, "before-30"), (7, "before-7"),
            (2, "before-7"), (1, "before-1"), (0, "before-1"), (-1, "overdue-1"),
            (-7, "overdue-1"), (-8, "overdue-2"), (-14, "overdue-2"), (-15, "overdue-3"),
        ):
            with self.subTest(days=days):
                self.assertEqual(review_reminder_slot(today + timedelta(days=days), today), expected)


class ExerciseTests(unittest.TestCase):
    COMPLETE = (date(2026, 11, 17), "Effective", "Recovered within target.", ["Met", "Partially Met"])

    def test_completed_exercise_requires_full_evidence(self):
        exercise_completion("Completed", *self.COMPLETE)

    def test_incomplete_evidence_blocks_completion(self):
        conducted, result, summary, outcomes = self.COMPLETE
        for case in (
            (None, result, summary, outcomes),
            (conducted, "", summary, outcomes),
            (conducted, result, "  ", outcomes),
            (conducted, result, summary, []),
            (conducted, result, summary, ["Met", "Not Assessed"]),
            (conducted, result, summary, ["Met", None]),
        ):
            with self.subTest(case=case), self.assertRaises(ValueError):
                exercise_completion("Completed", *case)

    def test_other_statuses_do_not_require_evidence(self):
        for status in ("Planned", "In Progress", "Cancelled"):
            with self.subTest(status=status):
                exercise_completion(status, None, None, None, [])


class CallTreeTests(unittest.TestCase):
    def test_complete_cascade_is_accepted(self):
        call_tree_structure(
            [("bcm", None), ("exec", "bcm"), ("it", "bcm"), ("vendor", "it")], True)

    def test_draft_allows_partial_cascade(self):
        call_tree_structure([("bcm", None)], False)
        call_tree_structure([("exec", "bcm"), ("bcm", None)], False)

    def test_structural_defects_always_rejected(self):
        for members in (
            [("bcm", None), ("bcm", None)],          # duplicate contact
            [("bcm", "bcm")],                        # calls themselves
            [("exec", "ghost"), ("bcm", None)],      # caller is not a member
        ):
            for complete in (False, True):
                with self.subTest(members=members, complete=complete), \
                        self.assertRaises(ValueError):
                    call_tree_structure(members, complete)

    def test_activation_requires_reachable_members(self):
        for members in (
            [("bcm", None)],                                      # too small
            [("a", "b"), ("b", "a")],                             # no initiator (cycle)
            [("bcm", None), ("a", "b"), ("b", "a")],              # orphaned cycle
        ):
            with self.subTest(members=members), self.assertRaises(ValueError):
                call_tree_structure(members, True)

    def test_span_of_control_flags_only_overloaded_callers(self):
        seven = [("root", None)] + [(f"m{i}", "root") for i in range(7)]
        self.assertEqual(call_tree_span(seven), [])
        eight = [("root", None)] + [(f"m{i}", "root") for i in range(8)]
        self.assertEqual(call_tree_span(eight), [("root", 8)])

    def test_span_ignores_self_calls_and_unknown_callers(self):
        self.assertEqual(call_tree_span(
            [("a", "a")] + [(f"m{i}", "ghost") for i in range(9)]), [])


class IncidentTests(unittest.TestCase):
    def test_resolution_requires_time_order_and_summary(self):
        incident_lifecycle("Resolved", "2026-11-20 09:00:00", "2026-11-20 11:30:00", "Restored.")
        for status, detected, resolved, summary in (
            ("Resolved", "2026-11-20 09:00:00", None, "Restored."),
            ("Closed", "2026-11-20 09:00:00", "2026-11-20 08:00:00", "Restored."),
            ("Resolved", "2026-11-20 09:00:00", "2026-11-20 11:30:00", "  "),
        ):
            with self.subTest(status=status), self.assertRaises(ValueError):
                incident_lifecycle(status, detected, resolved, summary)

    def test_open_statuses_need_no_resolution(self):
        for status in ("Open", "Investigating", "Mitigated"):
            with self.subTest(status=status):
                incident_lifecycle(status, "2026-11-20 09:00:00", None, None)


class CrisisTests(unittest.TestCase):
    def test_stand_down_requires_time_order_and_outcome(self):
        crisis_closure("Stood Down", "2026-11-20 09:00:00", "2026-11-20 18:00:00", "Contained.")
        for status, declared, stood_down, outcome in (
            ("Stood Down", "2026-11-20 09:00:00", None, "Contained."),
            ("Closed", "2026-11-20 09:00:00", "2026-11-20 08:00:00", "Contained."),
            ("Closed", "2026-11-20 09:00:00", "2026-11-20 18:00:00", ""),
        ):
            with self.subTest(status=status), self.assertRaises(ValueError):
                crisis_closure(status, declared, stood_down, outcome)

    def test_active_statuses_need_no_outcome(self):
        for status in ("Declared", "Managing"):
            with self.subTest(status=status):
                crisis_closure(status, "2026-11-20 09:00:00", None, None)


class DependencyTests(unittest.TestCase):
    def test_exactly_one_target_is_required(self):
        dependency_target("app-a", None, "srv-1", None)
        for targets in ((None, None, None), ("app-b", "srv-1", None),
                        ("app-b", "srv-1", "db-1")):
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                dependency_target("app-a", *targets)

    def test_self_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            dependency_target("app-a", "app-a", None, None)
