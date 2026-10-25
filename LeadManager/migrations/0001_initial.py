from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

def seed_defaults(apps, schema_editor):
    LeadSource=apps.get_model("LeadManager","LeadSource")
    Service=apps.get_model("LeadManager","Service")
    for name in ["Website","Google Ads","Meta Ads","Instagram","Facebook","LinkedIn","WhatsApp","Referral","Cold Outreach","Google Maps","Other"]:
        LeadSource.objects.get_or_create(name=name)
    for name in ["Website Development","SEO","Google Ads","Meta Ads","Social Media Marketing","Branding","E-commerce","UI/UX Design","Content Marketing","Maintenance"]:
        Service.objects.get_or_create(name=name)

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
      migrations.CreateModel(name="LeadSource",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
        ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
        ("name",models.CharField(max_length=80,unique=True)),("is_active",models.BooleanField(default=True))]),
      migrations.CreateModel(name="Service",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
        ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
        ("name",models.CharField(max_length=120,unique=True)),("is_active",models.BooleanField(default=True))]),
      migrations.CreateModel(name="Lead",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
        ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
        ("name",models.CharField(max_length=160)),("company",models.CharField(blank=True,max_length=180)),("email",models.EmailField(blank=True,max_length=254)),("phone",models.CharField(blank=True,max_length=40)),("website",models.URLField(blank=True)),
        ("country",models.CharField(blank=True,max_length=80)),("state",models.CharField(blank=True,max_length=100)),("city",models.CharField(blank=True,max_length=100)),
        ("stage",models.CharField(choices=[("new","New"),("contacted","Contacted"),("qualified","Qualified"),("proposal","Proposal Sent"),("negotiation","Negotiation"),("won","Won"),("lost","Lost"),("nurture","Nurture")],db_index=True,default="new",max_length=30)),
        ("temperature",models.CharField(choices=[("cold","Cold"),("warm","Warm"),("hot","Hot")],default="warm",max_length=10)),
        ("priority",models.CharField(choices=[("low","Low"),("medium","Medium"),("high","High"),("urgent","Urgent")],default="medium",max_length=10)),
        ("estimated_value",models.DecimalField(decimal_places=2,default=0,max_digits=14)),("probability",models.PositiveSmallIntegerField(default=10)),
        ("next_follow_up",models.DateTimeField(blank=True,db_index=True,null=True)),("last_contacted",models.DateTimeField(blank=True,null=True)),
        ("tags",models.CharField(blank=True,max_length=300)),("notes",models.TextField(blank=True)),("lost_reason",models.CharField(blank=True,max_length=255)),("consent_to_contact",models.BooleanField(default=True)),
        ("owner",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="owned_leads",to=settings.AUTH_USER_MODEL)),
        ("service",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="leads",to="LeadManager.service")),
        ("source",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="leads",to="LeadManager.leadsource"))],
        options={"ordering":["-updated_at"],}),
      migrations.CreateModel(name="Activity",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
        ("activity_type",models.CharField(choices=[("call","Call"),("email","Email"),("whatsapp","WhatsApp"),("meeting","Meeting"),("note","Note"),("status","Status Update")],default="note",max_length=20)),
        ("subject",models.CharField(max_length=180)),("body",models.TextField(blank=True)),("due_at",models.DateTimeField(blank=True,null=True)),("completed",models.BooleanField(default=True)),
        ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
        ("lead",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="activities",to="LeadManager.lead"))],
        options={"ordering":["-created_at"]}),
      migrations.CreateModel(name="Task",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
        ("title",models.CharField(max_length=200)),("description",models.TextField(blank=True)),("due_at",models.DateTimeField()),("status",models.CharField(choices=[("open","Open"),("in_progress","In Progress"),("done","Done")],default="open",max_length=20)),
        ("assigned_to",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="lead_tasks",to=settings.AUTH_USER_MODEL)),
        ("lead",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="tasks",to="LeadManager.lead"))]),
      migrations.CreateModel(name="Deal",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
        ("value",models.DecimalField(decimal_places=2,default=0,max_digits=14)),("expected_close",models.DateField(blank=True,null=True)),("status",models.CharField(choices=[("open","Open"),("won","Won"),("lost","Lost")],default="open",max_length=20)),("proposal_url",models.URLField(blank=True)),("notes",models.TextField(blank=True)),
        ("lead",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="deal",to="LeadManager.lead")),
        ("service",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to="LeadManager.service"))]),
      migrations.CreateModel(name="LeadNote",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("body",models.TextField(blank=False)),
        ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),("lead",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="lead_notes",to="LeadManager.lead"))]),
      migrations.AddIndex(model_name="lead",index=models.Index(fields=["stage","owner"],name="LeadManager__stage_o_6e43f1_idx")),
      migrations.AddIndex(model_name="lead",index=models.Index(fields=["next_follow_up"],name="LeadManager__next_fo_6d8c10_idx")),
      migrations.RunPython(seed_defaults,migrations.RunPython.noop),
    ]
