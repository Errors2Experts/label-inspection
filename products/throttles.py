from rest_framework.throttling import SimpleRateThrottle


class ProductLookupThrottle(SimpleRateThrottle):
    """Protects the external product API from being hammered (per logged-in user)."""

    scope = 'product_lookup'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
