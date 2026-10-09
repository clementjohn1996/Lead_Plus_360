# LeadPlus-360 Guide

Internal system for our IT company (software/web development, digital marketing, SEO, ad-video production). It combines CRM, HR onboarding, face-recognition attendance with geofencing, and employee performance scoring with a TV display. The same content is available in-app at `/guide/`.

## Roles
Super Admin > Management > HR > Project Managers, BD Managers, BD Team Leads, BD Executives > Digital Marketing, Graphic Designers, Videographers, Video Editors, Developers. The Super Admin can add roles at **Roles & access**.

## Everyone
- **Attendance**: allow camera and location, enrol your face once, then punch in/out. Punches outside the office radius are flagged.
- **My onboarding**: finish your checklist; some steps need HR/manager approval.
- **My performance**: your score, KPIs, rank.

## Sales roles
Add leads, log activities, schedule follow-ups, use the pipeline. Executives see own leads, Team Leads their team's, Managers and above all.

## HR
Employees > New (creates login, role, manager and auto-generates the onboarding checklist); Onboarding board and approvals; Attendance today / Monthly report; Office locations (lat, long, radius); reset a face.

## Super Admin
Roles & access; Onboarding workflows (role, then department, then default match; optional approvals); KPI setup; TV displays (`/tv/<token>/`, link-protected, rotates through employees); Django admin.

## First-day setup
1. Office locations 2. Roles 3. Workflows 4. KPIs 5. Add employees 6. Staff enrol faces 7. Create TV display

## Run
`.\venv\Scripts\activate`, `python manage.py migrate`, `python manage.py runserver`, then open http://127.0.0.1:8000/.

## BDE targets, colours, PIP and appraisals

- Each Business Development Executive has a monthly target (default 2,00,000, change under **BDE targets & rules**; per-person target on the same page).
- Revenue = leads/deals marked **Won** and owned by the BDE, counted in the month they were won.
- The target is split into 10 slabs: 1-5 Red, 6-8 Yellow, 9-10 Green. Above 100% shows "Target Exceeded".
- Over the last 4 completed months: 2 Red in a row or 4 Yellow in a row = PIP (draft created for HR to activate); 3 Yellow + 1 Green = Neutral; 2 Yellow + 2 Green or 3+ Green = Appraisal review. PIP wins over appraisal.
- Monthly run: `python manage.py calculate_bde_performance` (schedule it on the 1st); the **Recalculate** button does the same.
- Pages: Performance > BDE targets, Performance calendar, Appraisals; Admin > BDE targets & rules, Performance audit log.


## Delivery workflow

Use **Delivery Workflow** to follow a client/project from commercial acquisition to production:

1. BDE wins the lead.
2. LeadPlus-360 creates a delivery work item for each mapped service.
3. BDM accepts the work and routes it to a Project Manager.
4. Project Manager creates individual execution assignments.
5. Developers / Digital Marketing / Graphic Design / Video team members accept and update their own work.
6. Work moves through In Progress → Review → Completed.
7. The system records every handoff and completion event and feeds delivery activity into employee KPIs.
