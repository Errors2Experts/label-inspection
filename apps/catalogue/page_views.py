"""Server-rendered shells for the Product Catalogue screens (FDS 10.2). Data comes from /api/products/.
All roles may use the catalogue (FDS 7.2), so only login is enforced."""

from apps.accounts.page_views import PageView


class ProductListPage(PageView):
    """Product list with search and category filter. The Manual Product Entry card sits on this page and stays
    closed until "+ Add Product" or a row's Edit button opens it."""

    template_name = 'catalogue/product_list.html'
    mode = ''  # '' | 'add' | 'edit' (the form opens on load for the last two)

    def get_context_data(self, **kwargs):
        return super().get_context_data(mode=self.mode, **kwargs)


class ProductFormPage(ProductListPage):
    """/products/add/ and /products/<id>/edit/ open the same page with the entry form already showing."""


class ProductDetailPage(PageView):
    template_name = 'catalogue/product_detail.html'
