from django.core import exceptions
from django.utils import six

from .fields import Field


class Options(object):
    def __init__(self, model, filename):
        self.model = model
        self.filename = filename
        self.fields = None


class ImportBase(type):
    def __new__(cls, name, bases, attrs):
        super_new = super(ImportBase, cls).__new__
        parents = [b for b in bases if isinstance(b, ImportBase)]
        if not parents:
            return super_new(cls, name, bases, attrs)

        attr_meta = attrs.pop('Meta', None)
        new_class = super_new(cls, name, bases, attrs)

        if not attr_meta:
            meta = getattr(new_class, 'Meta', None)
        else:
            meta = attr_meta

        new_class._meta = Options(meta.model, meta.filename)
        new_class._meta.fields = {}
        for attr_name in attrs:
            attr = getattr(new_class, attr_name)
            if isinstance(attr, Field):
                new_class._meta.fields[attr.name] = attr_name

        return new_class


class ModelImport(six.with_metaclass(ImportBase)):
    """
    Maps import fields to model fields
    """
    def __init__(self, data=None):
        self.data = data or {}
        self.cleaned_data = {}
        self.errors = {}
        self.clean_fields()

    def clean_fields(self):
        """
        Cleans all fields and sets self.errors containing a dict
        of all validation errors if any occur.
        """

        errors = {}
        cleaned_data = {}
        for import_name, field_name in self._meta.fields.iteritems():
            f = getattr(self, field_name)
            try:
                val = f.clean(self.data[import_name])
                cleaned_data[field_name] = val
            except exceptions.ValidationError as e:
                errors[import_name] = e.error_list

        self.errors = errors
        self.cleaned_data = cleaned_data

    def is_valid(self):
        return not self.errors

    def get_or_create(self):
        """
        Runs Meta.model get_or_create for fields marked with upsert=True
        """
        upsert_data = {}
        for field_name in self._meta.fields.itervalues():
            f = getattr(self, field_name)
            if f.upsert:
                upsert_data[field_name] = self.cleaned_data[field_name]

        if upsert_data:
            instance = self._meta.model.objects.get_or_create(**upsert_data)[0]
        else:
            instance = self._meta.model()

        return instance

    def save(self):
        if self.is_valid():
            instance = self.get_or_create()
            for field_name, field_value in self.cleaned_data.iteritems():
                setattr(instance, field_name, field_value)
            instance.save()
