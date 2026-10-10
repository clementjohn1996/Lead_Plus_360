# LeadPlus-360

Internal operations platform for an IT services company (software & web app development, digital marketing, SEO, ad video production).

## Modules
- **CRM (LeadManager)** - leads, pipeline, tasks, activities, CSV export. BDS executives see only their own leads.
- **HR** - employee records, role-based accounts, automated onboarding checklists (default template seeded), documents.
- **Attendance** - face recognition (OpenCV YuNet + SFace) with geolocation geofencing against office locations.
- **Performance** - KPIs (auto-computed from CRM/attendance or manually entered), monthly scores, leaderboard.
- **TV display** - a secret URL `/tv/<token>/` that cycles through each employee's performance. Create it in Performance > TV displays.

## Setup
Use the installer for a clean database and an initial super admin account:

```bat
install.bat
```

The installer asks for the initial super admin username, email and password, clears any existing SQLite database, creates the standard org roles, and starts the app without seeding demo data.

If you prefer to set it up manually:

```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_employees   # employee records for existing users
python manage.py bootstrap_admin --username admin --password Admin@12345 --email admin@leadplus360.local
python manage.py runserver
```

### First login

A fresh ZIP does not include the SQLite database. After `migrate`, create the first login with:

```bash
python manage.py createsuperuser
```

Then sign in at `http://127.0.0.1:8000/login/` using that username and password. The login form also accepts an existing user's email address.

For demo data only, run `python manage.py seed_demo_data`; the demo password is `1234`.

## Notes
- Camera and geolocation need HTTPS in production (localhost works).
- HR must add office locations (Attendance > Offices) before office-based staff can punch in.
- Face matching has no liveness/anti-spoof detection; geofence, audit snapshots and attempt logs are the mitigations.
- Snapshots are stored in `private_media/` and served only through permission-checked views.
- Roles (top to bottom): Super Admin, Management, HR, Project Manager / BD Manager, BD Team Lead, BD Executive, then Digital Marketing, Graphic Designer, Videographer, Video Editor, Developer. Only a Super Admin can grant Super Admin or Management.
## Custom roles & workflows
- Super Admin: **Roles & access** (/roles/) creates roles with capability flags (CRM, lead scope, team manager, HR, privileged).
- **Onboarding workflows** (/hr/workflows/) define step checklists with optional approval (HR, reporting manager or Super Admin). Templates match by role, then department, then default.

## BDE performance management

The `Performance` module includes the BDE target/performance system:
- Default monthly BDE target: ₹2,00,000, with per-employee overrides.
- Ten achievement slabs by default: Red 1–5, Yellow 6–8, Green 9–10.
- Revenue is calculated from currently Won CRM leads owned by the BDE. A linked Deal value is preferred; otherwise `Lead.estimated_value` is used. The month is based on the latest Won status-history timestamp, with `updated_at` as fallback.
- Closed months retain their historical target when revenue is recalculated after a later target change.
- The latest four completed months drive PIP/appraisal/neutral evaluation. Employees with insufficient history remain `Insufficient Data`.
- Two consecutive Red months or four consecutive Yellow months trigger PIP, with PIP taking priority over appraisal.
- Two Yellow + two Green or three+ Green months trigger appraisal; three Yellow + one Green is Neutral.
- Management has a dashboard, employee profile, calendar, alerts, audit log and CSV export. HR can configure rules and targets; managers can review their direct-report BDEs and add PIP review notes.
- Monthly processing is idempotent and can be run manually with `python manage.py calculate_bde_performance` or scheduled with the operating system's scheduler (for example Windows Task Scheduler or cron).

### Database migration

This update does not introduce a new database model, so no new migration is required. The existing `Performance` migrations, including `0004_bde_performance`, must be applied with:

```bash
python manage.py migrate
```

### Manual verification

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py calculate_bde_performance
```


## LeadPlus-360 Delivery Workflow (v1.2)

The delivery workflow now tracks accountability beyond BDE performance:

`BDE → BDM → Project Manager → Execution Team → Review → Completion`

- A won lead with a mapped service automatically creates a Delivery Work Item.
- The BDE is recorded as the source owner.
- The BDM accepts/routes the work.
- The BDM assigns a Project Manager.
- The Project Manager assigns one or more execution tasks to developers, digital marketers, graphic designers, videographers, or video editors.
- Each employee updates their own assignment status/progress.
- The Project Manager can review and close the project.
- Every handoff is recorded in a workflow event trail.
- Delivery KPIs are added to the existing employee performance engine: assignments received, work completed, on-time completion, and completion rate.
- Existing won leads can be migrated with:
  `python manage.py sync_delivery_work`

### First-time update

Run:

`python manage.py migrate`

Then, for existing won leads:

`python manage.py sync_delivery_work`

Open:

`/delivery/`

### If you cannot log in

Use the active database used by your current project to create/reset an administrator:

```bash
python manage.py bootstrap_admin --username admin --password Admin@12345
```

Then sign in at `http://127.0.0.1:8000/login/` with `admin` / `Admin@12345`.

You can choose your own credentials, for example:

```bash
python manage.py bootstrap_admin --username clement --password YourStrongPassword123! --email you@example.com
```

## Work Calendar & Delivery Planning

LeadPlus-360 now includes a delivery work calendar under `/delivery/calendar/`. When a BDE converts a lead to **Won**, the lead editor routes the BDE directly into delivery planning.

### Workflow
1. **BDE converts lead → Won** → delivery plan screen opens automatically.
2. Select a **preset package** or use a custom package. Presets are seeded by migration and can be changed from **Delivery → Work calendar → Packages**.
3. Package templates generate tasks such as **🎬 Video, 🎨 Posters, 📣 Meta Ads, 💻 Website and 🔎 SEO**.
4. Each task has owner, start/due dates, progress and status. Video tasks have dedicated **shoot, edited/draft and final** milestones.
5. BDE submits the complete plan to the **BDM**.
6. BDM/Management can review, edit dates/scope and either **Approve** or **Request changes**.
7. Approved plans remain visible to **BDEs, BDMs, Project Managers, Management, HR/Admin and assigned delivery staff** according to their role.
8. The calendar displays each task with its relevant emoji/icon and optionally supports an animated GIF URL per package/task template.

### Default preset packages
- Digital Marketing + Website + SEO
- Digital Marketing
- Website + SEO

### Setup
Run `python manage.py migrate` after updating the project. If you use the included Windows installer, run it once and then start Django normally. The new migration creates the work-calendar tables and seeds the default package templates.
