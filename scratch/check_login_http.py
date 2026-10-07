import urllib.request

try:
    req = urllib.request.Request(
        'http://127.0.0.1:8000/login/',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as resp:
        print('HTTP Status:', resp.status)
        html = resp.read().decode('utf-8')
        print('HTML Length:', len(html))
        print('Has Title:', 'Sign In' in html)
        print('Has CSRF:', 'csrfmiddlewaretoken' in html)
        print('Has Username Input:', 'id="username"' in html)
        print('Has Password Input:', 'id="password"' in html)
        print('Has Password Toggle:', 'id="togglePassword"' in html)
        print('Has Brand Logo:', 'Dhvani_Patalia.jpeg' in html)
        print('Has Register Link:', '/register/' in html)
        print('Has Forgot Password Link:', '/forgot-password/' in html)
        print('Has Home Link:', 'Back to Home' in html)
except Exception as e:
    print('Error:', e)
