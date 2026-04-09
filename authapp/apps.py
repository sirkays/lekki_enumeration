from django.apps import AppConfig


class AuthConfig(AppConfig):
    name = 'authapp'
    
    def ready(self):
        import authapp.signals 