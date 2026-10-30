"""Authentication presentation contracts; runnable without the application database."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AuthDesignTests(unittest.TestCase):
    def test_auth_pages_share_restrained_styles(self):
        login = (ROOT / 'templates/login.html').read_text()
        self.assertIn("filename='auth.css'", login)
        self.assertIn('auth-layout', login)
        for name in ('forgot_password', 'reset_password'):
            source = (ROOT / f'templates/{name}.html').read_text()
            self.assertIn('{% extends "login.html" %}', source)
            self.assertNotIn('animate-in', source)
        css = (ROOT / 'static/auth.css').read_text()
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('@media', css)
        self.assertIn(':focus-visible', css)
        self.assertNotRegex(login + css, r'@keyframes|orb-ring|class="scan"|animation:')

    def test_existing_form_contracts_are_preserved(self):
        for name, fields in {
            'login': ('username', 'password'),
            'forgot_password': ('username',),
            'reset_password': ('password', 'confirm_password'),
        }.items():
            source = (ROOT / f'templates/{name}.html').read_text()
            self.assertIn('method="post"', source)
            self.assertIn('name="csrf_token" value="{{ csrf_token() }}"', source)
            for field in fields:
                self.assertRegex(source, rf'<input[^>]*name="{field}"[^>]*required')
            if name != 'login':
                self.assertNotRegex(source, r'<form[^>]*action=')
                self.assertIn("url_for('login')", source)
        login = (ROOT / 'templates/login.html').read_text()
        self.assertIn('action="{{ url_for(\'login\') }}"', login)
        self.assertIn('{% if forgot_password_enabled %}', login)
        self.assertIn("url_for('forgot_password')", login)
        # Check template markers individually: these are UI contracts, not credentials.
        self.assertIn('branding_logo', login)
        self.assertIn('brand_display', login)
        self.assertIn('dynamic_favicon', login)
        self.assertIn('get_flashed_messages', login)
        self.assertIn('toggle-password', login)
        self.assertIn('pw-eye-open', login)
        self.assertIn('pw-eye-closed', login)
        self.assertIn('localStorage.getItem', login)
        self.assertIn('Show password', login)
        self.assertIn('Hide password', login)

    def test_rendered_forms_branding_and_recovery_visibility(self):
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
        except ImportError:
            self.skipTest('Jinja2 unavailable; source contracts still run with stdlib')
        env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape())
        def url_for(endpoint, **kwargs):
            if endpoint == 'static':
                return '/static/' + kwargs['filename']
            return '/' + endpoint
        for name in ('login', 'forgot_password', 'reset_password'):
            for enabled in (False, True):
                with self.subTest(page=name, recovery=enabled):
                    html = env.get_template(name + '.html').render(
                        branding_name='Acme', branding_logo='logo.png',
                        app_version='1.2.3', forgot_password_enabled=enabled,
                        url_for=url_for, csrf_token=lambda: 'csrf-test',
                        get_flashed_messages=lambda **kw: [('error', '<unsafe>')],
                    )
                    self.assertIn('Acme Asset Manager', html)
                    self.assertIn('/static/uploads/logo.png', html)
                    self.assertIn('value="csrf-test"', html)
                    self.assertIn('&lt;unsafe&gt;', html)
                    self.assertEqual(html.count('<form '), 1)
                    self.assertEqual('href="/forgot_password"' in html, name == 'login' and enabled)
                    if name != 'login':
                        self.assertNotIn('autocomplete="current-password"', html)
                        self.assertIn('id="theme-toggle"', html)
                        self.assertIn('href="/login"', html)
                    if name == 'reset_password':
                        self.assertIn('name="confirm_password"', html)


if __name__ == '__main__':
    unittest.main()
