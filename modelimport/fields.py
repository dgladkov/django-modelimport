# -*- coding: utf-8 -*-
import decimal
from django.core import exceptions, validators
from django.utils.encoding import smart_text
from django.utils.translation import ugettext_lazy as _


__all__ = ['Field', 'CharField', 'BooleanField', 'DecimalField', 'SimpleFKField']


class Field(object):
    """
    Desribes import field and converts data
    """

    empty_values = list(validators.EMPTY_VALUES)
    default_error_messages = {
        'invalid_choice': _('Value %(value)r is not a valid choice.'),
        'blank': _('This field cannot be blank.'),
    }

    def __init__(self, name, coerce=None, default=None, required=False,
                 upsert=False, choices=None, validators=None):
        self.name = name
        self.coerce = coerce
        self.default = default
        self.required = required
        self.upsert = upsert
        self.choices = choices
        self.validators = validators or []

        messages = {}
        for c in reversed(self.__class__.__mro__):
            messages.update(getattr(c, 'default_error_messages', {}))
        self.error_messages = messages

    def validate(self, value):
        if self.choices and value not in self.empty_values:
            if value not in self.choices:
                raise exceptions.ValidationError(
                    self.error_messages['invalid_choice'],
                    code='invalid_choice',
                    params={'value': value},
                )

        if self.required and value in self.empty_values:
            raise exceptions.ValidationError(self.error_messages['blank'], code='blank')

    def clean(self, value):
        self.validate(value)
        self.run_validators(value)
        value = self.to_python(value)
        return value

    def to_python(self, value):
        if self.coerce:
            return self.coerce(value)
        return value

    def run_validators(self, value):
        errors = []
        for v in self.validators:
            try:
                v(value)
            except exceptions.ValidationError as e:
                if hasattr(e, 'code') and e.code in self.error_messages:
                    e.message = self.error_messages[e.code]
                errors.extend(e.error_list)

        if errors:
            raise exceptions.ValidationError(errors)


class CharField(Field):

    def __init__(self, *args, **kwargs):
        min_length = kwargs.pop('min_length', None)
        max_length = kwargs.pop('max_length', None)

        super(CharField, self).__init__(*args, **kwargs)

        if self.default is None:
            self.default = ''

        if min_length is not None:
            self.validators.append(validators.MinLengthValidator(int(min_length)))
        if max_length is not None:
            self.validators.append(validators.MaxLengthValidator(int(max_length)))

    def to_python(self, value):
        if isinstance(value, basestring) or value is None:
            return value
        return smart_text(value)


class BooleanField(Field):

    default_error_messages = {
        'invalid': _("'%(value)s' value must be either True or False."),
    }

    def __init__(self, *args, **kwargs):
        self.choices = ('0', '1')
        super(BooleanField, self).__init__(*args, **kwargs)

        if self.coerce is None:
            self.coerce = lambda x: bool(int(x))

    def to_python(self, value):
        if value in (True, False):
            return bool(value)
        if value in ('t', 'True', 'true', '1'):
            return True
        if value in ('f', 'False', 'false', '0'):
            return False
        raise exceptions.ValidationError(
            self.error_messages['invalid'],
            code='invalid',
            params={'value': value},
        )


class DecimalField(Field):

    default_error_messages = {
        'invalid': _("'%(value)s' value must be a decimal number."),
    }

    def __init__(self, *args, **kwargs):
        super(DecimalField, self).__init__(*args, **kwargs)
        if self.default is None:
            self.default = '0'

    def to_python(self, value):
        if value is None:
            return value
        try:
            return decimal.Decimal(value)
        except decimal.InvalidOperation:
            raise exceptions.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
                params={'value': value},
            )


class SimpleFKField(CharField):
    """
    Biased logic to convert plain strings like "myname" to FK get_or_create()
    """
    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop('model')
        self.field_name = kwargs.pop('field_name')

        super(SimpleFKField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        return self.model.objects.get_or_create(**{self.field_name: value})[0]
