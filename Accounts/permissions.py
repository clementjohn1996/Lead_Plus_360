from Control.permissions import permission_required, can_manage_accounts

accounts_required = permission_required(can_manage_accounts)
