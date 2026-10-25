from django.core import mail
from django.test import TestCase
from django.urls import reverse

from Control.test_helpers import make_user
from LeadManager.models import Lead

from . import importer, profiler, services, writer
from .models import Campaign, OutboxMessage, OutreachSettings, Prospect


def prospect(company="Acme Dental", email="owner@acme.example", **kw):
    p = Prospect.objects.create(company=company, email=email, contact_name="Riya Shah", **kw)
    return p


class ProfilerTests(TestCase):
    def test_analyze_finds_signals_offline(self):
        found, data = profiler.analyze(
            "<html><body><script src='https://connect.facebook.net/x.js'></script>Website by Pixel Studio</body></html>",
            "http://acme.example")
        for key in ("NO_HTTPS", "NOT_MOBILE_FRIENDLY", "NO_ONLINE_BOOKING", "RUNNING_META_ADS", "INCUMBENT_AGENCY"):
            self.assertIn(key, found)

    def test_private_addresses_are_refused(self):
        with self.assertRaises(ValueError):
            profiler.fetch("http://127.0.0.1/")

    def test_only_confirmed_signals_are_kept_and_score_set(self):
        p = prospect(website="")
        profiler.scan_prospect(p, ["NO_WEBSITE"])
        p.refresh_from_db()
        self.assertEqual(p.signals, ["NO_WEBSITE"])
        self.assertGreaterEqual(p.score, 5)
        p2 = prospect("Other", "o@other.example", website="")
        profiler.scan_prospect(p2, [])
        p2.refresh_from_db()
        self.assertEqual(p2.signals, [])


class ImportTests(TestCase):
    def test_csv_rows_import_and_skip_duplicates(self):
        user = make_user("imp", role="bd_executive")
        Lead.objects.create(name="Existing", email="old@x.example")
        rows = [["Company Name", "E-mail", "Mobile", "Website"],
                ["Zen Cafe", "hi@zen.example", "999999999", "zen.example"],
                ["Zen Cafe again", "hi@zen.example", "", ""],
                ["Old Co", "old@x.example", "", ""],
                ["", "", "", ""]]
        summary = importer.import_prospects(rows, user)
        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["duplicates"], 2)
        self.assertEqual(Prospect.objects.get().domain, "zen.example")


class WriterTests(TestCase):
    def test_sequence_is_short_and_clean(self):
        p = prospect()
        p.set_signals(["NO_ONLINE_BOOKING"])
        c = Campaign.objects.create(name="C", offer="build booking sites that turn visitors into appointments")
        seq = writer.build_sequence(p, c, OutreachSettings.get_solo())
        self.assertEqual(len(seq), 3)
        for step, subject, body in seq:
            self.assertLessEqual(writer.words(body), writer.WORD_LIMITS[step] + 15)
            self.assertEqual(writer.violations(subject + body), [])
        self.assertIn("Acme Dental", seq[0][2])


class ReplyAndConvertTests(TestCase):
    def test_reply_classification(self):
        self.assertEqual(services.classify_reply("Please remove me from your list"), "unsubscribe")
        self.assertEqual(services.classify_reply("Not interested, thanks"), "not_interested")
        self.assertEqual(services.classify_reply("Sounds good, send pricing"), "interested")
        self.assertEqual(services.classify_reply("I am out of office until Monday"), "out_of_office")

    def test_reply_cancels_queue_and_convert_creates_lead(self):
        user = make_user("rep", role="bd_executive")
        p = prospect()
        c = Campaign.objects.create(name="C", offer="x")
        OutboxMessage.objects.create(prospect=p, campaign=c, step=1, subject="s", body="b", status="approved")
        services.log_reply(p, "Interested, please call me", user)
        p.refresh_from_db()
        self.assertEqual(p.status, "replied")
        self.assertEqual(OutboxMessage.objects.get().status, "cancelled")
        lead, created = services.convert_to_lead(p, user)
        self.assertTrue(created)
        self.assertEqual(lead.owner, user)
        self.assertEqual(lead.source.name, "Outreach")
        p.refresh_from_db()
        self.assertEqual(p.status, "converted")


class SendingTests(TestCase):
    def setUp(self):
        self.user = make_user("sender", role="bd_executive")
        self.cfg = OutreachSettings.get_solo()
        self.p = prospect()
        self.p.owner = self.user
        self.p.set_signals(["NO_ONLINE_BOOKING"])
        self.p.save()
        self.c = Campaign.objects.create(name="C", offer="build booking sites", status="active", filters={})

    def test_draft_approve_send_with_footer_and_cap(self):
        created, _ = services.draft_campaign(self.c, self.user)
        self.assertEqual(created, 3)
        first = OutboxMessage.objects.get(step=1)
        first.status = "approved"
        first.save()
        sent, _ = services.send_due()
        self.assertEqual(sent, 1)
        self.assertIn("Unsubscribe", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.p.email])
        # step 2 not due yet (needs a gap) even if approved
        second = OutboxMessage.objects.get(step=2)
        second.status = "approved"
        second.save()
        self.assertEqual(services.send_due()[0], 0)

    def test_paused_and_cap_block_sending(self):
        services.draft_campaign(self.c, self.user)
        OutboxMessage.objects.filter(step=1).update(status="approved")
        self.cfg.sending_paused = True
        self.cfg.save()
        self.assertEqual(services.send_due()[0], 0)
        self.cfg.sending_paused = False
        self.cfg.daily_cap = 0
        self.cfg.save()
        self.assertEqual(services.send_due()[0], 0)

    def test_unsubscribed_prospect_is_never_emailed(self):
        services.draft_campaign(self.c, self.user)
        OutboxMessage.objects.filter(step=1).update(status="approved")
        self.client.post(reverse("outreach_unsubscribe", args=[self.p.unsubscribe_token]))
        self.assertEqual(services.send_due()[0], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_approval_desk_flow(self):
        services.draft_campaign(self.c, self.user)
        self.client.force_login(self.user)
        msg = OutboxMessage.objects.get(step=1)
        self.client.post(reverse("outreach_outbox"), {"id": msg.pk, "action": "approve", "subject": "Hello", "body": "Edited body"})
        msg.refresh_from_db()
        self.assertEqual((msg.status, msg.subject, msg.body), ("approved", "Hello", "Edited body"))


class CohortTests(TestCase):
    def test_must_and_exclude(self):
        user = make_user("coh", role="super_admin", superuser=True)
        a = prospect("A", "a@a.example")
        a.set_signals(["NO_HTTPS", "BLOG_STALE"])
        a.score = 6
        a.save()
        b = prospect("B", "b@b.example")
        b.set_signals(["NO_HTTPS"])
        b.score = 3
        b.save()
        self.assertEqual(services.cohort(user, {"must": ["NO_HTTPS"]}).count(), 2)
        self.assertEqual(services.cohort(user, {"must": ["NO_HTTPS"], "exclude": ["BLOG_STALE"]}).count(), 1)
        self.assertEqual(services.cohort(user, {"min_score": 5}).count(), 1)
