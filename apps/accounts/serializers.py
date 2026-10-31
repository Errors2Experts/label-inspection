from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


def _check_unique_email(value, instance=None):
    value = value.strip().lower()
    qs = User.objects.filter(email__iexact=value)
    if instance is not None:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError('A user with this email already exists.')
    return value


class UserSerializer(serializers.ModelSerializer):
    """Read / update representation used by the admin user-management screens."""

    full_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'phone',
            'employee_id',
            'is_active',
            'last_login',
            'created_at',
            'full_name',
            'initials',
        ]
        read_only_fields = ['id', 'username', 'last_login', 'created_at']

    def validate_email(self, value):
        return _check_unique_email(value, self.instance)

    def validate_employee_id(self, value):
        return value or None


class UserCreateSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['password']
        read_only_fields = ['id', 'last_login', 'created_at']  # username is settable on create

    def validate_username(self, value):
        # Login matches usernames case-insensitively, so 'Admin' and 'admin' must not coexist.
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('A user with that username already exists.')
        return value

    def validate(self, attrs):
        # Run the configured password policy with user context (similarity check).
        candidate = User(
            username=attrs.get('username', ''),
            email=attrs.get('email', ''),
            first_name=attrs.get('first_name', ''),
            last_name=attrs.get('last_name', ''),
        )
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'phone',
            'employee_id',
            'last_login',
            'full_name',
            'initials',
        ]
        read_only_fields = ['id', 'username', 'role', 'employee_id', 'last_login']

    def validate_email(self, value):
        return _check_unique_email(value, self.instance)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text='Username or email')
    password = serializers.CharField(style={'input_type': 'password'}, trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(style={'input_type': 'password'})
    new_password = serializers.CharField(style={'input_type': 'password'})

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(style={'input_type': 'password'})
