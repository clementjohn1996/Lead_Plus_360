from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from Control.tests import make_user
from LeadManager.models import Lead
from Performance import bde
from Performance.models import (
    Appraisal, BDEConfig, ImprovementPlan, MonthlyPerformance, PerformanceAlert,
)


def make_bde(name, manager=None):
    user = make_user(name, role="bd_executive")
    emp = user.employee
    emp.date_of_joining = date(2024, 1, 1)
    emp.manager = manager
    emp.save()
    return emp


def put(emp, month, colour):
    slab = {"red": 0, "yellow": 6, "green": 10}[colour]
    return MonthlyPerformance.objects.create(
        employee=emp, month=month, target=200000, revenue=slab * 20000, achievement_pct=slab * 10,
        slab=slab, colour=colour)


class RuleTests(TestCase):
    def test_slabs_and_colours(self):
        cfg = BDEConfig.get()
        cases = [(0, 0, "red"), (80000, 4, "red"), (110000, 6, "yellow"), (160000, 8, "yellow"),
                 (162000, 9, "green"), (185000, 10, "green"), (240000, 10, "green")]
        for revenue, slab, colour in cases:
            got = bde.slab_for(Decimal(revenue), Decimal(200000), cfg)
            self.assertEqual(got, slab, revenue)
            self.assertEqual(bde.colour_for_slab(got, cfg), colour)
        self.assertEqual(bde.slab_for(Decimal(90000), Decimal(300000), cfg), 3)

    def test_segments_are_ten_columns(self):
        segs = bde.segments(7)
        self.assertEqual(len(segs), 10)
        self.assertEqual([s["colour"] for s in segs], ["red"] * 5 + ["yellow"] * 3 + ["green"] * 2)
        self.assertEqual(sum(s["filled"] for s in segs), 7)

    def test_patterns(self):
        R, Y, G = "red", "yellow", "green"
        table = [
            ([R, R, R, R], "pip"), ([G, R, R, G], "pip"), ([R, G, R, G], "neutral"),
            ([R, G, Y, R], "neutral"), ([Y, Y, Y, Y], "pip"), ([Y, Y, Y, G], "neutral"),
            ([Y, Y, G, G], "appraisal"), ([G, G, G, Y], "appraisal"), ([G, G, G, G], "appraisal"),
            ([R, R, G, G], "pip"), ([Y, G, Y, Y], "neutral"), ([Y, None, Y, Y], "insufficient"),
            ([G, G], "insufficient"), ([R, Y, R, Y], "neutral"),
        ]
        for colours, expected in table:
            self.assertEqual(bde.evaluate(colours)[0], expected, colours)
        self.assertEqual(bde.evaluate([R, R])[0], "insufficient")

    def test_prorated_target(self):
        emp = make_bde("joiner")
        emp.date_of_joining = date(2026, 6, 16)
        self.assertEqual(bde.prorated_target(emp, date(2026, 6, 1), Decimal(300000)), Decimal("150000.00"))
        self.assertIsNone(bde.prorated_target(emp, date(2026, 5, 1), Decimal(300000)))


class RevenueAndEngineTests(TestCase):
    def test_won_revenue_and_cancellation(self):
        emp = make_bde("rev")
        lead = Lead.objects.create(name="Acme", owner=emp.user, stage="new", estimated_value=240000)
        lead.stage = "won"
        lead.save()
        rec = MonthlyPerformance.objects.get(employee=emp, month=timezone.localdate().replace(day=1))
        self.assertEqual(rec.revenue, 240000)
        self.assertEqual(rec.achievement_pct, Decimal("120.00"))
        self.assertEqual(rec.slab, 10)
        self.assertIn("exceeded", rec.category)
        self.assertTrue(PerformanceAlert.objects.filter(employee=emp, kind="target_exceeded").exists())
        lead.stage = "lost"
        lead.save()
        rec.refresh_from_db()
        self.assertEqual(rec.revenue, 0)

    def test_custom_target_and_audit(self):
        emp = make_bde("custom")
        bde.set_target(emp, 300000)
        self.assertEqual(bde.target_for(emp), 300000)
        with self.assertRaises(ValueError):
            bde.set_target(emp, 0)
        self.assertTrue(emp.performance_alerts.count() == 0)

    def test_two_red_months_create_one_pip_and_one_alert(self):
        emp = make_bde("reds")
        today = date(2026, 10, 15)
        for m, c in [(6, "green"), (7, "green"), (8, "red"), (9, "red")]:
            put(emp, date(2026, m, 1), c)
        for _ in range(2):
            self.assertEqual(bde.process_employee(emp, today), "pip")
        plan = ImprovementPlan.objects.get()
        self.assertEqual((plan.status, plan.auto_created), ("draft", True))
        self.assertEqual(PerformanceAlert.objects.filter(kind="pip_red").count(), 1)
        self.assertFalse(Appraisal.objects.exists())

    def test_appraisal_created_once_and_pip_wins(self):
        emp = make_bde("stars")
        today = date(2026, 10, 15)
        for m, c in [(6, "green"), (7, "green"), (8, "green"), (9, "yellow")]:
            put(emp, date(2026, m, 1), c)
        bde.process_employee(emp, today)
        bde.process_employee(emp, today)
        self.assertEqual(Appraisal.objects.count(), 1)
        self.assertFalse(ImprovementPlan.objects.exists())
        bad = make_bde("mixed")
        for m, c in [(6, "red"), (7, "red"), (8, "green"), (9, "green")]:
            put(bad, date(2026, m, 1), c)
        bde.process_employee(bad, today)
        self.assertEqual(ImprovementPlan.objects.filter(employee=bad).count(), 1)
        self.assertFalse(Appraisal.objects.filter(employee=bad).exists())

    def test_unique_month_and_negative_revenue(self):
        emp = make_bde("dup")
        put(emp, date(2026, 5, 1), "red")
        with self.assertRaises(IntegrityError), transaction.atomic():
            put(emp, date(2026, 5, 1), "green")
        with self.assertRaises(IntegrityError), transaction.atomic():
            MonthlyPerformance.objects.create(employee=emp, month=date(2026, 4, 1), target=1, revenue=-5)

    def test_monthly_command_is_idempotent(self):
        emp = make_bde("cmd")
        bde.run_monthly()
        count = MonthlyPerformance.objects.filter(employee=emp).count()
        bde.run_monthly()
        self.assertEqual(MonthlyPerformance.objects.filter(employee=emp).count(), count)


    def test_closed_month_keeps_historical_target_after_target_change(self):
        emp = make_bde("target_history")
        bde.set_target(emp, 200000)
        old = bde.recalc_month(emp, date(2026, 8, 1), today=date(2026, 10, 15))
        self.assertEqual(old.target, Decimal("200000.00"))
        bde.set_target(emp, 300000)
        old = bde.recalc_month(emp, date(2026, 8, 1), today=date(2026, 10, 15))
        current = bde.recalc_month(emp, date(2026, 10, 1), today=date(2026, 10, 15))
        self.assertEqual(old.target, Decimal("200000.00"))
        self.assertEqual(current.target, Decimal("300000.00"))


class PermissionTests(TestCase):
    def test_access_rules(self):
        hr = make_user("hr", role="hr")
        mgr_user = make_user("mgr", role="bd_manager")
        a = make_bde("a", manager=mgr_user.employee)
        b = make_bde("b")
        rec = bde.recalc_month(a, timezone.localdate())

        self.client.force_login(a.user)
        self.assertEqual(self.client.get(reverse("bde_me")).status_code, 200)
        self.assertEqual(self.client.get(reverse("bde_profile", args=[a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("bde_profile", args=[b.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("bde_dashboard")).status_code, 403)
        self.assertEqual(self.client.post(reverse("bde_record_update", args=[rec.pk]), {"manager_remarks": "x"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("bde_config")).status_code, 403)

        self.client.force_login(mgr_user)
        self.assertEqual(self.client.get(reverse("bde_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("pip_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("bde_profile", args=[a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("bde_profile", args=[b.pk])).status_code, 403)
        self.client.post(reverse("bde_record_update", args=[rec.pk]), {"manager_remarks": "Good", "colour_override": "green"})
        rec.refresh_from_db()
        self.assertEqual((rec.manager_remarks, rec.colour_override), ("Good", ""))
        self.assertEqual(self.client.get(reverse("bde_config")).status_code, 403)

        self.client.force_login(hr)
        for name in ["bde_dashboard", "bde_calendar", "bde_config", "bde_audit", "bde_appraisals", "bde_export", "pip_list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.client.post(reverse("bde_record_update", args=[rec.pk]), {"manager_remarks": "ok", "colour_override": "green"})
        rec.refresh_from_db()
        self.assertEqual(rec.colour_override, "green")
        self.client.post(reverse("bde_target_update", args=[a.pk]), {"target": "300,000"})
        self.assertEqual(bde.target_for(a), 300000)
        self.assertEqual(self.client.post(reverse("bde_recalculate")).status_code, 302)
        resp = self.client.post(reverse("bde_config"), {"form": "config", "default_target": "250000", "slabs": 10,
            "red_max": 5, "yellow_max": 8, "red_pip_months": 2, "yellow_pip_months": 4, "window_months": 4,
            "appraisal_green_months": 3, "appraisal_mixed_green": 2, "appraisal_mixed_yellow": 2,
            "neutral_yellow": 3, "neutral_green": 1})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BDEConfig.get().default_target, 250000)
