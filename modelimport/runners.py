# -*- coding: utf-8 -*-
import os
from csv import excel
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from unicodecsv import DictReader


class excel_semicolon(excel):
    delimiter = ';'


class RegistryMixin(object):
    """
    Registers targets to uninstanciated class
    """
    _registry = None

    @classmethod
    def register(cls, target):
        if cls._registry is None:
            cls._registry = {}
        cls._registry[target.__name__] = target

    @property
    def registry(self):
        registry = self._registry or {}
        for line in registry.iteritems():
            yield line


class BaseRunner(RegistryMixin):
    """
    Base import runner class. All subclasses must define their own read() methods.
    """
    NOT_STARTED = 0
    IN_PROGRESS = 1
    FAILED = 2
    SUCCESS = 3

    status_choices = {
        NOT_STARTED: _('Not Started'),
        IN_PROGRESS: _('In Progress'),
        FAILED: _('Failed'),
        SUCCESS: _('Success'),
    }

    _status = NOT_STARTED

    def __init__(self, import_root, encoding, continue_on_error=True):
        self.import_root = import_root
        self.encoding = encoding
        self.errors = {}
        self.continue_on_error = continue_on_error

    @property
    def status(self):
        return self.status_choices[self._status]

    def _set_status(self, value):
        self._status = value

    def read(self, filepath):
        """
        This field must be overriden by subclasses
        """
        raise NotImplementedError

    @transaction.atomic
    def run(self):
        self._set_status(self.IN_PROGRESS)
        global_errors = {}

        for name, cls in self.registry:
            local_errors = []
            filepath = os.path.join(self.import_root, cls._meta.filename)

            for row in self.read(filepath):
                modelimport = cls(row)
                if modelimport.is_valid():
                    modelimport.save()
                else:
                    local_errors.append(modelimport.errors)
                    self._set_status(self.FAILED)
                    if not self.continue_on_error:
                        break

            global_errors[name] = local_errors

        self.errors = global_errors

        if self._status != self.FAILED:
            self._set_status(self.SUCCESS)


class CsvRunner(BaseRunner):
    def __init__(self, *args, **kwargs):
        self.dialect = kwargs.pop('dialect', excel)
        super(CsvRunner, self).__init__(*args, **kwargs)

    def read(self, filepath):
        with open(filepath, 'r') as f:
            reader = DictReader(f, encoding=self.encoding, dialect=self.dialect)
            for row in reader:
                yield row
