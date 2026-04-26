import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher_string.dart';
import '../services/api_client.dart';
import '../services/token_store.dart';
import 'asset_types_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _urlController = TextEditingController();
  final _userController = TextEditingController();
  final _passController = TextEditingController();
  bool _loading = false;
  bool _obscurePassword = true;
  String? _error;
  String _scheme = 'https://';
  bool _remember = false;
  static const _repoUrl = 'https://github.com/tayyabtahir143/AssetManager';
  static const _privacyUrl =
      'https://privacypolicy.assetmanager.tayyabtahir.com';

  @override
  void initState() {
    super.initState();
    final store = TokenStore();
    _tryAutoLogin();
    store.getBaseUrl().then((value) {
      if (!mounted || value.isEmpty) return;
      if (value.startsWith('http://')) {
        _scheme = 'http://';
        _urlController.text = value.substring('http://'.length);
      } else if (value.startsWith('https://')) {
        _scheme = 'https://';
        _urlController.text = value.substring('https://'.length);
      } else {
        _urlController.text = value;
      }
      setState(() {});
    });
    store.getRememberCredentials().then((value) {
      if (!mounted) return;
      setState(() => _remember = value);
    });
    store.getSavedUsername().then((value) {
      if (!mounted || value == null) return;
      setState(() => _userController.text = value);
    });
    store.getSavedPassword().then((value) {
      if (!mounted || value == null) return;
      setState(() => _passController.text = value);
    });
  }

  Future<void> _tryAutoLogin() async {
    final store = TokenStore();
    final baseUrl = await store.getBaseUrl();
    if (baseUrl.isEmpty) return;
    final accessToken = await store.getAccessToken();
    final refreshToken = await store.getRefreshToken();
    if ((accessToken == null || accessToken.isEmpty) &&
        (refreshToken == null || refreshToken.isEmpty)) {
      return;
    }
    if (!mounted) return;
    setState(() => _loading = true);
    bool authenticated = accessToken != null && accessToken.isNotEmpty;
    if (!authenticated && refreshToken != null && refreshToken.isNotEmpty) {
      final api = ApiClient(store);
      authenticated = await api.refreshToken();
    }
    if (!mounted) return;
    if (authenticated) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AssetTypesScreen()),
      );
      return;
    }
    setState(() => _loading = false);
  }

  Future<void> _login() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final store = TokenStore();
      await store.clearTokens();
      final host = _urlController.text.trim();
      final username = _userController.text.trim();
      final password = _passController.text.trim();
      if (host.isEmpty || username.isEmpty || password.isEmpty) {
        setState(() {
          _loading = false;
          _error = 'Please fill all fields.';
        });
        return;
      }
      final baseUrl = '$_scheme$host';
      await store.setBaseUrl(baseUrl);
      final api = ApiClient(store);
      final token = await api.login(username, password);
      if (token == null) {
        setState(() {
          _loading = false;
          _error = 'Login failed.';
        });
        return;
      }
      await store.saveCredentials(
        username: username,
        password: password,
        remember: _remember,
      );
      await store.setTokens(token.accessToken, token.refreshToken);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AssetTypesScreen()),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Login failed. Please check your server and credentials.';
      });
    }
  }

  Future<void> _openRepo() async {
    await launchUrlString(_repoUrl, mode: LaunchMode.externalApplication);
  }

  Future<void> _openPrivacy() async {
    if (_privacyUrl.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Privacy policy URL is not configured.')),
      );
      return;
    }
    await launchUrlString(_privacyUrl, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFEFF3FF), Color(0xFFF7F9FF)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                height: 46,
                                width: 46,
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(14),
                                  gradient: const LinearGradient(
                                    colors: [
                                      Color(0xFF3B82F6),
                                      Color(0xFF7C3AED),
                                    ],
                                  ),
                                ),
                                child: Padding(
                                  padding: const EdgeInsets.all(8),
                                  child: Image.asset('assets/icon.png'),
                                ),
                              ),
                              const SizedBox(width: 12),
                              const Expanded(
                                child: Text(
                                  'IT Asset Manager',
                                  style: TextStyle(
                                    fontSize: 21,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            'Connect to your server and continue.',
                            style: TextStyle(
                              fontSize: 13,
                              color: Color(0xFF5B6B86),
                            ),
                          ),
                          const SizedBox(height: 20),
                          Row(
                            children: [
                              DropdownButton<String>(
                                value: _scheme,
                                items: const [
                                  DropdownMenuItem(
                                    value: 'http://',
                                    child: Text('http://'),
                                  ),
                                  DropdownMenuItem(
                                    value: 'https://',
                                    child: Text('https://'),
                                  ),
                                ],
                                onChanged: (value) {
                                  if (value == null) return;
                                  setState(() {
                                    _scheme = value;
                                    _loading = false;
                                    _error = null;
                                  });
                                },
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: TextField(
                                  controller: _urlController,
                                  decoration: const InputDecoration(
                                    labelText: 'Server Host',
                                  ),
                                  onChanged: (_) {
                                    if (_loading || _error != null) {
                                      setState(() {
                                        _loading = false;
                                        _error = null;
                                      });
                                    }
                                  },
                                ),
                              ),
                            ],
                          ),
                          if (_scheme == 'http://')
                            const Padding(
                              padding: EdgeInsets.only(top: 8),
                              child: Text(
                                'Warning: http:// is insecure. Use https:// in production.',
                                style: TextStyle(
                                  color: Colors.redAccent,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _userController,
                            decoration: const InputDecoration(
                              labelText: 'Username',
                            ),
                            onChanged: (_) {
                              if (_loading || _error != null) {
                                setState(() {
                                  _loading = false;
                                  _error = null;
                                });
                              }
                            },
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _passController,
                            obscureText: _obscurePassword,
                            decoration: InputDecoration(
                              labelText: 'Password',
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword
                                      ? Icons.visibility_outlined
                                      : Icons.visibility_off_outlined,
                                ),
                                onPressed: () {
                                  setState(
                                    () => _obscurePassword = !_obscurePassword,
                                  );
                                },
                              ),
                            ),
                            onChanged: (_) {
                              if (_loading || _error != null) {
                                setState(() {
                                  _loading = false;
                                  _error = null;
                                });
                              }
                            },
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Checkbox(
                                value: _remember,
                                onChanged: (value) {
                                  if (value == null) return;
                                  setState(() => _remember = value);
                                },
                              ),
                              const Text('Remember credentials'),
                            ],
                          ),
                          const SizedBox(height: 8),
                          if (_error != null)
                            Text(
                              _error!,
                              style: const TextStyle(color: Colors.redAccent),
                            ),
                          const SizedBox(height: 8),
                          ElevatedButton(
                            onPressed: _loading ? null : _login,
                            child: _loading
                                ? const SizedBox(
                                    height: 18,
                                    width: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Text('Sign in'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  OutlinedButton.icon(
                    onPressed: _openRepo,
                    icon: Icon(Icons.code, color: colors.primary),
                    label: const Text('Get Asset Manager Server (GitHub)'),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _openPrivacy,
                    child: const Text('Privacy Policy'),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Server must be running to use this app.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
