"""Server-rendered shells for the Compliance Rules screens (FDS 12.2). Data comes from /api/rules/ etc.
Rule management is Admin/Supervisor (FDS 7.2); results are viewable by every role (API scopes inspectors to their own)."""

from apps.accounts.page_views import STAFF, PageView


class _Staff(PageView):
    roles = STAFF


class RulesOverviewPage(_Staff):
    template_name = 'compliance/rules_overview.html'


class RuleFormPage(_Staff):
    """Add Rule (mode='add') / Edit Rule (mode='edit' - saving changed logic creates a new version)."""

    template_name = 'compliance/rule_form.html'
    mode = 'add'

    def get_context_data(self, **kwargs):
        return super().get_context_data(mode=self.mode, **kwargs)


class RuleVersionsPage(_Staff):
    template_name = 'compliance/rule_versions.html'


class CategoriesPage(_Staff):
    template_name = 'compliance/categories.html'


class PackFormPage(_Staff):
    template_name = 'compliance/pack_form.html'
    mode = 'add'

    def get_context_data(self, **kwargs):
        return super().get_context_data(mode=self.mode, **kwargs)


class EvaluatePage(_Staff):
    template_name = 'compliance/evaluate.html'


class ResultListPage(PageView):
    template_name = 'compliance/result_list.html'


class ResultDetailPage(PageView):
    template_name = 'compliance/result_detail.html'


class ViolationsPage(PageView):
    template_name = 'compliance/violations.html'
