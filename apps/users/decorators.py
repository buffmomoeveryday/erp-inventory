from django.contrib.auth.decorators import permission_required


def erp_perm(codename: str):
    return permission_required(f"users.{codename}", raise_exception=True)
