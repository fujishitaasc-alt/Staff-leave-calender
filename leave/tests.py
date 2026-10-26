from datetime import date, time
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.urls import reverse
from .models import Staff, Leave, LeaveType, Threshold
from .services import overlaps


class LeaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = Staff.objects.create_user(
            username="alice", password="Sensible-pass-9827", name="架空 あお", role="PT"
        )
        cls.bob = Staff.objects.create_user(
            username="bob", password="Sensible-pass-9827", name="架空 そら", role="PT"
        )
        cls.helper = Staff.objects.create_user(
            username="helper",
            password="Sensible-pass-9827",
            name="架空 はる",
            role="ASSISTANT",
        )
        cls.admin = Staff.objects.create_superuser(
            username="boss", password="Admin-pass-9827", name="架空 管理"
        )
        cls.type = LeaveType.objects.create(name="休暇")
        cls.day = date(2026, 11, 2)

    def record(self, staff=None, kind="TIME", start=time(10), end=time(11), save=True):
        r = Leave(
            staff=staff or self.alice,
            date=self.day,
            kind=kind,
            start=start,
            end=end,
            leave_type=self.type,
        )
        r.full_clean()
        if save:
            r.save()
        return r

    def payload(self, **kw):
        return {
            "date": self.day.isoformat(),
            "kind": "TIME",
            "start": "10:00",
            "end": "11:00",
            "leave_type": self.type.pk,
            **kw,
        }

    def test_lunch_is_excluded(self):
        r = self.record(start=time(12, 15), end=time(14, 16))
        self.assertEqual(r.minutes, 31)
        self.assertEqual(r.intervals(), [(735, 750), (840, 856)])

    def test_minute_precision(self):
        self.assertEqual(self.record(start=time(8, 31), end=time(8, 32)).minutes, 1)

    def test_invalid_times(self):
        for a, b in [
            (time(8, 29), time(10)),
            (time(17), time(18, 1)),
            (time(10), time(10)),
            (time(11), time(10)),
            (time(12, 30), time(14)),
            (time(13), time(13, 59)),
            (time(10, 0, 1), time(11)),
        ]:
            with self.subTest(a=a, b=b), self.assertRaises(ValidationError):
                self.record(start=a, end=b)

    def test_missing_times(self):
        with self.assertRaises(ValidationError):
            self.record(start=None)

    def test_full_and_halves(self):
        self.assertEqual(self.record(kind="FULL", save=False).minutes, 480)
        self.assertEqual(self.record(kind="AM", save=False).intervals(), [(510, 750)])
        self.assertEqual(self.record(kind="PM", save=False).minutes, 240)

    def test_duplicate_prevented(self):
        self.record(kind="AM")
        with self.assertRaises(ValidationError):
            self.record(start=time(12), end=time(14, 10))

    def test_touching_boundaries_allowed(self):
        self.record(end=time(11))
        self.record(start=time(11), end=time(12))
        self.assertEqual(Leave.objects.count(), 2)

    def test_lunch_does_not_create_false_overlap(self):
        self.record(start=time(12), end=time(13))
        self.record(start=time(13), end=time(15))
        self.assertEqual(Leave.objects.count(), 2)

    def test_update_self_no_false_duplicate(self):
        r = self.record()
        r.full_clean()

    def test_distinct_time_not_daily_count(self):
        a = self.record(start=time(9), end=time(10))
        b = self.record(staff=self.bob, start=time(10), end=time(11))
        self.assertEqual(max(x["count"] for x in overlaps([a, b], "PT", None)), 1)

    def test_concurrent_and_role_threshold(self):
        a = self.record(kind="FULL")
        b = self.record(staff=self.bob, start=time(10), end=time(11))
        h = self.record(staff=self.helper, kind="AM")
        slots = overlaps([a, b, h], "PT", 2)
        self.assertEqual(
            [(x["label"], x["count"], x["warn"]) for x in slots],
            [
                ("08:30〜10:00", 1, False),
                ("10:00〜11:00", 2, True),
                ("11:00〜12:30", 1, False),
                ("14:00〜18:00", 1, False),
            ],
        )
        self.assertEqual(overlaps([a, b, h], "ASSISTANT", None)[0]["count"], 1)

    def test_same_person_counted_once_even_bad_legacy_rows(self):
        a = self.record(save=False)
        b = self.record(start=time(10, 30), end=time(11, 30), save=False)
        self.assertEqual(max(x["count"] for x in overlaps([a, b], "PT", None)), 1)

    def test_threshold_unset_and_validation(self):
        a = self.record()
        self.assertFalse(any(x["warn"] for x in overlaps([a], "PT", None)))
        with self.assertRaises(ValidationError):
            Threshold(role="PT", count=0).full_clean()

    def test_anonymous_no_data(self):
        r = self.record()
        for path in [
            "/",
            "/mine/",
            "/new/",
            f"/leave/{r.pk}/",
            f"/leave/{r.pk}/cancel/",
            "/admin/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)

    def test_login_and_invalid_login(self):
        self.assertFalse(self.client.login(username="alice", password="wrong"))
        self.assertTrue(
            self.client.login(username="alice", password="Sensible-pass-9827")
        )
        self.assertContains(self.client.get("/"), "共有カレンダー")

    def test_disabled_login_and_existing_session(self):
        self.client.force_login(self.alice)
        Staff.objects.filter(pk=self.alice.pk).update(is_active=False)
        for path in ["/", "/mine/", "/new/", "/admin/"]:
            self.assertEqual(self.client.get(path).status_code, 302)
        self.assertFalse(
            self.client.login(username="alice", password="Sensible-pass-9827")
        )

    def test_other_staff_cannot_edit_or_cancel(self):
        r = self.record(staff=self.bob)
        self.client.force_login(self.alice)
        for path in [f"/leave/{r.pk}/", f"/leave/{r.pk}/cancel/"]:
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post(path, self.payload()).status_code, 403)
        self.assertTrue(Leave.objects.filter(pk=r.pk).exists())

    def test_identity_cannot_be_forged(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            "/new/",
            self.payload(staff=self.bob.pk, is_staff="true", is_superuser="true"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Leave.objects.get().staff_id, self.alice.pk)
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)

    def test_staff_admin_denied(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get("/admin/leave/staff/").status_code, 302)
        self.assertEqual(
            self.client.post(
                f"/admin/leave/staff/{self.alice.pk}/change/", {"is_superuser": "on"}
            ).status_code,
            302,
        )
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_superuser)

    def test_admin_can_edit_other_staff(self):
        r = self.record(staff=self.bob)
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(
                f"/leave/{r.pk}/", self.payload(start="11:15", end="12:15")
            ).status_code,
            302,
        )
        r.refresh_from_db()
        self.assertEqual(r.start, time(11, 15))
        self.assertContains(self.client.get("/admin/leave/staff/"), "架空 あお")

    def test_admin_deactivate_preserves_history(self):
        r = self.record()
        self.alice.is_active = False
        self.alice.save()
        self.assertEqual(Leave.objects.get(pk=r.pk).staff_id, self.alice.pk)
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(f"/admin/leave/staff/{self.alice.pk}/delete/").status_code,
            403,
        )

    def test_admin_change_role_and_threshold(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/leave/threshold/add/", {"role": "PT", "count": "2", "_save": "保存"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Threshold.objects.get(role="PT").count, 2)
        response = self.client.post(
            f"/admin/leave/staff/{self.bob.pk}/change/",
            {
                "username": "bob",
                "name": "架空 そら",
                "role": "ASSISTANT",
                "is_active": "on",
                "date_joined_0": "2026-10-26",
                "date_joined_1": "12:00:00",
                "_save": "保存",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.role, "ASSISTANT")

    def test_warning_does_not_block(self):
        Threshold.objects.create(role="PT", count=1)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post("/new/", self.payload()).status_code, 302)
        self.assertContains(self.client.get("/?month=2026-11"), "注意")

    def test_duplicate_rejected_at_http(self):
        self.record()
        self.client.force_login(self.alice)
        self.assertContains(self.client.post("/new/", self.payload()), "重複")
        self.assertEqual(Leave.objects.count(), 1)

    def test_lunch_only_rejected_at_http(self):
        self.client.force_login(self.alice)
        self.assertContains(
            self.client.post("/new/", self.payload(start="12:30", end="14:00")),
            "昼休憩だけ",
        )
        self.assertEqual(Leave.objects.count(), 0)

    def test_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        self.assertEqual(client.post("/new/", self.payload()).status_code, 403)

    def test_cancel_requires_post(self):
        r = self.record()
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(f"/leave/{r.pk}/cancel/").status_code, 200)
        self.assertTrue(Leave.objects.filter(pk=r.pk).exists())
        self.assertEqual(self.client.post(f"/leave/{r.pk}/cancel/").status_code, 302)
        self.assertFalse(Leave.objects.filter(pk=r.pk).exists())

    def test_month_filter_list_and_all_labels(self):
        self.record(kind="AM")
        self.record(staff=self.helper, kind="PM")
        self.client.force_login(self.alice)
        response = self.client.get("/?month=2026-11&role=PT&view=list")
        self.assertContains(response, "架空 あお")
        self.assertNotContains(response, "架空 はる")
        self.assertNotContains(response, 'class="calendar"')
        self.assertEqual(self.client.get("/?month=invalid").status_code, 200)

    def test_persistence_across_clients(self):
        self.client.force_login(self.alice)
        self.client.post("/new/", self.payload())
        second = Client()
        second.force_login(self.bob)
        self.assertContains(second.get("/?month=2026-11"), "10:00〜11:00")

    def test_save_error_has_no_success(self):
        self.client.force_login(self.alice)
        with patch(
            "leave.forms.LeaveForm.save", side_effect=OperationalError("test failure")
        ):
            response = self.client.post("/new/", self.payload())
        self.assertContains(response, "保存できませんでした")
        self.assertNotContains(response, "保存しました。予定は全員に共有")
        self.assertEqual(Leave.objects.count(), 0)

    def test_initialization_repeatable(self):
        from django.core.management import call_command
        from io import StringIO

        call_command("init_leave", stdout=StringIO())
        t = Threshold.objects.get(role="PT")
        self.assertIsNone(t.count)
        t.count = 3
        t.save()
        call_command("init_leave", stdout=StringIO())
        self.assertEqual(Threshold.objects.get(role="PT").count, 3)

    def test_japan_timezone(self):
        from django.utils import timezone
        from datetime import datetime, timezone as tz

        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 10, 31, 16, 0, tzinfo=tz.utc),
        ):
            self.assertEqual(timezone.localdate(), date(2026, 11, 1))

    def test_admin_creates_staff(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/leave/staff/add/",
            {
                "username": "new_staff",
                "name": "架空 みず",
                "role": "ASSISTANT",
                "is_active": "on",
                "usable_password": "true",
                "password1": "New-person-6842!",
                "password2": "New-person-6842!",
                "_save": "保存",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = Staff.objects.get(username="new_staff")
        self.assertEqual(user.role, "ASSISTANT")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("New-person-6842!"))

    def test_disabled_cannot_post(self):
        self.client.force_login(self.alice)
        Staff.objects.filter(pk=self.alice.pk).update(is_active=False)
        self.assertEqual(self.client.post("/new/", self.payload()).status_code, 302)
        self.assertEqual(Leave.objects.count(), 0)

    def test_user_cannot_set_threshold(self):
        self.client.force_login(self.alice)
        self.assertEqual(
            self.client.post(
                "/admin/leave/threshold/add/", {"role": "PT", "count": 1}
            ).status_code,
            302,
        )
        self.assertEqual(Threshold.objects.count(), 0)

    def test_seed_refused_in_production(self):
        from django.core.management import call_command, CommandError

        with self.settings(DEMO=False), self.assertRaises(CommandError):
            call_command("seed_demo")

    def test_database_protects_staff_records(self):
        from django.db.models.deletion import ProtectedError

        self.record()
        with self.assertRaises(ProtectedError):
            self.alice.delete()

    def test_new_form_defaults_to_normal_leave_type(self):
        from .forms import LeaveForm

        form = LeaveForm(instance=Leave(staff=self.alice))
        self.assertEqual(form["leave_type"].value(), self.type.pk)


from django.test import TransactionTestCase
from django.db import connection, connections
from unittest import skipUnless
import threading


@skipUnless(connection.vendor == "postgresql", "PostgreSQLの行ロック専用検証")
class ConcurrentTests(TransactionTestCase):
    def test_simultaneous_same_staff_registration(self):
        staff = Staff.objects.create_user(
            username="race", password="Race-pass-8872", name="架空 同時"
        )
        lt = LeaveType.objects.create(name="休暇")
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(staff)
        barrier = threading.Barrier(2)
        outcomes = []
        errors = []

        def submit(client):
            try:
                barrier.wait(timeout=10)
                response = client.post(
                    "/new/", {"date": "2026-11-03", "kind": "AM", "leave_type": lt.pk}
                )
                outcomes.append(response.status_code)
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=submit, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(outcomes), [200, 302])
        self.assertEqual(Leave.objects.count(), 1)


class CommitFailureTests(TransactionTestCase):
    def test_commit_failure_does_not_report_success(self):
        staff = Staff.objects.create_user(
            username="commit", password="Commit-pass-9918", name="架空 保存"
        )
        kind = LeaveType.objects.create(name="休暇")
        self.client.force_login(staff)
        with patch.object(
            connection,
            "commit",
            side_effect=OperationalError("simulated commit failure"),
        ):
            response = self.client.post(
                "/new/", {"date": "2026-11-03", "kind": "AM", "leave_type": kind.pk}
            )
        self.assertContains(response, "保存できませんでした")
        self.assertNotContains(response, "保存しました。予定は全員に共有")
        self.assertEqual(Leave.objects.count(), 0)
