from django.contrib import admin

from .models import Milestone, Project, ProjectAccess, WorkflowStatus

admin.site.register([Project, ProjectAccess, Milestone, WorkflowStatus])
