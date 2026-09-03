class CabecalhosSegurancaMiddleware:
    """Apply a restrictive baseline without depending on an external proxy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
