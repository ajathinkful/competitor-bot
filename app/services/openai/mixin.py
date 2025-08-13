class OpenAIMixin:
    @staticmethod
    def paginate_decorator(fn):
        def inner(*args, **kwargs):
            resp = fn(*args, **kwargs)
            while True:
                for datum in resp.data:
                    yield datum

                if not getattr(resp, "has_next", False):
                    break

                resp = resp.get_next()

        return inner
