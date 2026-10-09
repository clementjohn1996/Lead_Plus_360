# LeadPlus-360 — Work Calendar Update

## What was added

The Delivery module now includes a complete **Work Calendar & Delivery Planning** workflow.

### BDE workflow
- A BDE changes a lead to **Won**.
- LeadPlus-360 automatically opens the delivery-plan screen.
- The BDE selects a preset package or creates/uses a custom package.
- Package templates automatically generate the required work items.
- The BDE sets milestone dates, assigns owners, adds notes and submits the plan to the BDM.

### Package examples
**Digital Marketing + Website + SEO** is seeded with:
- 🎬 Video production — shoot date, edited/draft date, final date
- 🎨 Poster creatives — start, draft/launch, final
- 📣 Meta Ads — setup/launch/review planning fields
- 💻 Website — start, draft/launch, final
- 🔎 SEO — audit/implementation/report planning fields

Packages are reusable. Management, BDMs and BD team users can create custom packages and package task templates from the package manager.

### BDM approval
A submitted plan enters **Pending BDM approval**.

The BDM can:
- review all client/package details;
- change dates and task details before approval;
- approve the plan and release it for delivery;
- request changes, returning it to the BDE.

### Visibility
The calendar is available to BDEs, BDMs, Project Managers, Management, HR/Admin and assigned delivery users according to their role. Management-level users see company delivery plans; delivery staff see work assigned to them.

### Calendar UI
Each calendar task shows its task icon and progress. Package templates can also store an optional GIF URL; when present, the GIF is displayed instead of the emoji/icon.

## Database
New migration:

`Delivery/migrations/0002_work_calendar.py`

It creates:
- `DeliveryPackage`
- `PackageTaskTemplate`
- `DeliveryPlan`
- `DeliveryCalendarTask`

The migration also seeds the initial package templates.

## Apply

```bash
python manage.py migrate
```

Then open:

```text
/delivery/calendar/
```

The existing Delivery workflow remains available at:

```text
/delivery/
```
