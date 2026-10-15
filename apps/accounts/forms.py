from django.contrib.auth.forms import AdminUserCreationForm as DjangoAdminUserCreationForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm

from .models import User


class AdminUserCreationForm(DjangoAdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserChangeForm(DjangoUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
