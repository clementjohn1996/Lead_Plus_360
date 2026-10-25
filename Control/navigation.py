"""Single source of truth for the sidebar.

Every item declares who may see it. The sidebar template just loops over the groups
returned by ``build_navigation`` so every page gets the same, duplicate-free menu and
nobody is shown a link to a module they cannot open. The checks mirror the decorators
on the target views.
"""
from .permissions import (
    can_manage_accounts, can_manage_team, can_use_crm, can_use_outreach, has_employee, is_admin, is_hr,
)


def _manager_or_hr(user):
    return can_manage_team(user) or is_hr(user)


def _delivery(user):
    return has_employee(user) or _manager_or_hr(user) or is_admin(user)


def _my_work(user):
    return has_employee(user)


def _always(user):
    return True


# (label, icon, url name, url names that mark the item active, visibility check)
NAV = [
    ("", [
        ("Home", "⌂", "home", ["home"], _always),
        ("User guide", "☰", "guide", ["guide"], _always),
    ]),
    ("My work", [
        ("Attendance", "●", "attendance", ["attendance"], _my_work),
        ("My onboarding", "✓", "my_onboarding", ["my_onboarding"], _my_work),
        ("My performance", "★", "performance_me", ["performance_me"], _my_work),
        ("My BDE target", "◆", "bde_me", ["bde_me"], lambda u: has_employee(u) and not _manager_or_hr(u)),
    ]),
    ("Growth engine", [
        ("Growth overview", "◎", "outreach_dashboard", ["outreach_dashboard"], can_use_outreach),
        ("Prospects", "⌕", "outreach_prospects",
         ["outreach_prospects", "outreach_prospect_detail", "outreach_prospect_new"], can_use_outreach),
        ("Import leads (Excel/CSV)", "⇪", "outreach_import", ["outreach_import"], can_use_outreach),
        ("Cohort builder", "◧", "outreach_cohorts", ["outreach_cohorts"], can_use_outreach),
        ("Campaigns", "✉", "outreach_campaigns",
         ["outreach_campaigns", "outreach_campaign_detail", "outreach_campaign_new"], can_use_outreach),
        ("Approval desk", "✔", "outreach_outbox", ["outreach_outbox"], can_use_outreach),
        ("Signals & settings", "⚙", "outreach_settings", ["outreach_settings"], can_use_outreach),
    ]),
    ("CRM", [
        ("CRM overview", "■", "leadplus_dashboard", ["leadplus_dashboard"], can_use_crm),
        ("Leads", "●", "leads", ["leads", "lead_detail", "lead_edit", "lead_create"], can_use_crm),
        ("Pipeline", "░", "pipeline", ["pipeline"], can_use_crm),
        ("Follow-ups", "✓", "tasks", ["tasks", "add_task"], can_use_crm),
        ("Quick lead", "⚡", "quick_lead", ["quick_lead"], can_use_crm),
        ("Export leads", "⤓", "export_leads", ["export_leads"], can_use_crm),
    ]),
    ("Delivery", [
        ("Delivery workflow", "↗", "delivery_dashboard", ["delivery_dashboard", "delivery_detail"], _delivery),
        ("Work calendar", "▦", "delivery_calendar", ["delivery_calendar", "delivery_calendar_date"], _delivery),
    ]),
    ("Finance", [
        ("Accounts overview", "₹", "accounts_dashboard", ["accounts_dashboard"], can_manage_accounts),
        ("Invoices", "▣", "account_invoices",
         ["account_invoices", "account_invoice_create", "account_invoice_detail"], can_manage_accounts),
        ("Customers", "☺", "account_customers", ["account_customers", "account_customer_create"], can_manage_accounts),
        ("Expenses", "−", "account_expenses", ["account_expenses", "account_expense_create"], can_manage_accounts),
    ]),
    ("Performance", [
        ("Leaderboard", "★", "performance", ["performance", "performance_employee"], can_manage_team),
        ("BDE targets", "◆", "bde_dashboard", ["bde_dashboard", "bde_profile"], _manager_or_hr),
        ("Performance calendar", "▦", "bde_calendar", ["bde_calendar"], _manager_or_hr),
        ("Appraisals", "↑", "bde_appraisals", ["bde_appraisals", "bde_appraisal"], _manager_or_hr),
        ("Improvement plans", "♒", "pip_list", ["pip_list", "pip_detail", "pip_create"], _manager_or_hr),
        ("Export BDE data", "⤓", "bde_export", ["bde_export"], _manager_or_hr),
    ]),
    ("People", [
        ("Employees", "☺", "hr_employees", ["hr_employees", "hr_employee_detail", "hr_employee_edit"], is_hr),
        ("Add employee", "＋", "hr_employee_create", ["hr_employee_create"], is_hr),
        ("Onboarding board", "♒", "hr_onboarding", ["hr_onboarding"], is_hr),
        ("Attendance today", "◷", "attendance_dashboard", ["attendance_dashboard"], is_hr),
        ("Monthly attendance", "▦", "attendance_monthly", ["attendance_monthly"], is_hr),
        ("KPI setup", "☰", "performance_kpis", ["performance_kpis", "performance_kpi_edit"], is_hr),
        ("Performance TV", "▣", "performance_tv_manage", ["performance_tv_manage", "performance_tv_action"], is_hr),
        ("BDE targets & rules", "♧", "bde_config", ["bde_config", "bde_target_update"], is_hr),
        ("Performance audit log", "☰", "bde_audit", ["bde_audit"], is_hr),
    ]),
    ("Administration", [
        ("Control center", "♧", "control_center", ["control_center"], is_admin),
        ("Office locations", "⌖", "attendance_offices", ["attendance_offices", "attendance_office_edit"], is_hr),
        ("Departments", "▦", "hr_departments", ["hr_departments"], is_admin),
        ("Roles & access", "☺", "roles", ["roles", "role_create", "role_edit", "role_detail"], is_admin),
        ("Onboarding workflows", "♒", "hr_workflows",
         ["hr_workflows", "hr_workflow_create", "hr_workflow_edit"], is_admin),
        ("Company branding", "✦", "branding", ["branding"], is_admin),
    ]),
]


def build_navigation(user, current_url_name):
    groups = []
    for title, items in NAV:
        rows = []
        for label, icon, url_name, active_names, check in items:
            try:
                allowed = check(user)
            except Exception:  # a broken check must never take the page down
                allowed = False
            if allowed:
                rows.append({
                    "label": label, "icon": icon, "url_name": url_name,
                    "active": current_url_name in active_names,
                })
        if rows:
            groups.append({"title": title, "items": rows})
    return groups


def guide_audience(user):
    """Which guide chapters apply to this user (drives the role-aware User guide)."""
    audience = {"everyone"}
    if has_employee(user):
        audience.add("employee")
    if can_use_crm(user):
        audience.add("crm")
    if can_use_outreach(user):
        audience.add("outreach")
    if can_manage_accounts(user):
        audience.add("accounts")
    if can_manage_team(user):
        audience.add("manager")
    if is_hr(user):
        audience.add("hr")
    if is_admin(user):
        audience.add("admin")
    if _delivery(user):
        audience.add("delivery")
    if _manager_or_hr(user):
        audience.add("bde_team")
    return audience
