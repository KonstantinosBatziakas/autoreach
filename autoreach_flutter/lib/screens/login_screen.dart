import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/auth_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  // ── View state ─────────────────────────────────────────────────────────────
  bool _showEmailForm = false;
  bool _isRegister = false;

  // ── Email form ─────────────────────────────────────────────────────────────
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl  = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passCtrl  = TextEditingController();
  bool _obscurePass = true;

  // ── Loading / error ────────────────────────────────────────────────────────
  String? _loadingProvider;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  // ── OAuth: open Render URL; deep-link callback handled in main.dart ───────
  Future<void> _oauthLogin(String provider) async {
    setState(() { _loadingProvider = provider; _error = null; });
    try {
      final uri = switch (provider) {
        'github'  => AuthService.githubAuthUrl(),
        'discord' => AuthService.discordAuthUrl(),
        'google'  => AuthService.googleAuthUrl(),
        _         => throw 'Unknown provider',
      };
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw 'Could not open browser';
      }
      // The app will receive autoreach://callback?token=... via deep link.
      // main.dart / AppLinksHandler picks that up and navigates to '/'.
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loadingProvider = null);
    }
  }

  // ── Email + password submit ────────────────────────────────────────────────
  Future<void> _emailSubmit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() { _loadingProvider = 'email'; _error = null; });
    try {
      final String token;
      if (_isRegister) {
        token = await AuthService.emailRegister(
          _nameCtrl.text.trim(),
          _emailCtrl.text.trim(),
          _passCtrl.text,
        );
      } else {
        token = await AuthService.emailLogin(
          _emailCtrl.text.trim(),
          _passCtrl.text,
        );
      }
      await AuthService.saveToken(token);
      if (mounted) Navigator.pushReplacementNamed(context, '/');
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loadingProvider = null);
    }
  }

  // ── Build ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0D0D1A), Color(0xFF141421), Color(0xFF1A1A2E)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 40),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _Logo(),
                  const SizedBox(height: 48),

                  if (!_showEmailForm) ...[
                    _oauthButton(
                      label: 'Continue with GitHub',
                      provider: 'github',
                      color: const Color(0xFF24292E),
                      borderColor: const Color(0xFF444466),
                      icon: const Icon(Icons.code, color: Colors.white, size: 20),
                    ),
                    const SizedBox(height: 12),
                    _oauthButton(
                      label: 'Continue with Discord',
                      provider: 'discord',
                      color: const Color(0xFF5865F2),
                      borderColor: const Color(0xFF5865F2),
                      icon: const Icon(Icons.discord, color: Colors.white, size: 20),
                    ),
                    const SizedBox(height: 12),
                    _oauthButton(
                      label: 'Continue with Google',
                      provider: 'google',
                      color: const Color(0xFF2A2A3E),
                      borderColor: const Color(0xFF444466),
                      icon: _GoogleIcon(),
                    ),
                    const SizedBox(height: 24),
                    Row(children: [
                      const Expanded(child: Divider(color: Color(0xFF333355))),
                      const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 12),
                        child: Text('or', style: TextStyle(color: Color(0xFF555577), fontSize: 12)),
                      ),
                      const Expanded(child: Divider(color: Color(0xFF333355))),
                    ]),
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF888AAA),
                          side: const BorderSide(color: Color(0xFF444466)),
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        onPressed: () => setState(() { _showEmailForm = true; _error = null; }),
                        child: const Text('Continue with Email'),
                      ),
                    ),
                  ] else ...[
                    _EmailForm(
                      formKey: _formKey,
                      nameCtrl: _nameCtrl,
                      emailCtrl: _emailCtrl,
                      passCtrl: _passCtrl,
                      obscurePass: _obscurePass,
                      isRegister: _isRegister,
                      loading: _loadingProvider == 'email',
                      onToggleObscure: () => setState(() => _obscurePass = !_obscurePass),
                      onSubmit: _emailSubmit,
                      onToggleMode: () => setState(() {
                        _isRegister = !_isRegister;
                        _error = null;
                      }),
                      onBack: () => setState(() { _showEmailForm = false; _error = null; }),
                    ),
                  ],

                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF6B6B).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFFFF6B6B).withOpacity(0.3)),
                      ),
                      child: Row(children: [
                        const Icon(Icons.error_outline, color: Color(0xFFFF6B6B), size: 16),
                        const SizedBox(width: 8),
                        Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFFFF6B6B), fontSize: 13))),
                      ]),
                    ),
                  ],

                  const SizedBox(height: 40),
                  const Text(
                    'Open source · Free forever · Self-hosted',
                    style: TextStyle(color: Color(0xFF444466), fontSize: 11),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _oauthButton({
    required String label,
    required String provider,
    required Color color,
    required Color borderColor,
    required Widget icon,
  }) {
    final loading = _loadingProvider == provider;
    return SizedBox(
      width: double.infinity,
      child: Material(
        color: color,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: (_loadingProvider != null) ? null : () => _oauthLogin(provider),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: borderColor.withOpacity(0.5)),
            ),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              loading
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : icon,
              const SizedBox(width: 12),
              Text(label, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
            ]),
          ),
        ),
      ),
    );
  }
}

// ── Email form widget ──────────────────────────────────────────────────────────
class _EmailForm extends StatelessWidget {
  final GlobalKey<FormState> formKey;
  final TextEditingController nameCtrl, emailCtrl, passCtrl;
  final bool obscurePass, isRegister, loading;
  final VoidCallback onToggleObscure, onSubmit, onToggleMode, onBack;

  const _EmailForm({
    required this.formKey, required this.nameCtrl, required this.emailCtrl,
    required this.passCtrl, required this.obscurePass, required this.isRegister,
    required this.loading, required this.onToggleObscure,
    required this.onSubmit, required this.onToggleMode, required this.onBack,
  });

  @override
  Widget build(BuildContext context) {
    return Form(
      key: formKey,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: Color(0xFF888AAA)),
            onPressed: onBack,
            padding: EdgeInsets.zero,
          ),
          Text(
            isRegister ? 'Create account' : 'Sign in',
            style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
          ),
        ]),
        const SizedBox(height: 20),

        if (isRegister) ...[
          _field(nameCtrl, 'Your name', Icons.person, validator: (v) =>
              (v == null || v.trim().isEmpty) ? 'Name is required' : null),
          const SizedBox(height: 14),
        ],

        _field(emailCtrl, 'Email address', Icons.email,
            keyboardType: TextInputType.emailAddress,
            validator: (v) => (v == null || !v.contains('@')) ? 'Enter a valid email' : null),
        const SizedBox(height: 14),

        _field(passCtrl, 'Password', Icons.lock,
            obscure: obscurePass,
            suffixIcon: IconButton(
              icon: Icon(obscurePass ? Icons.visibility : Icons.visibility_off,
                  color: const Color(0xFF888AAA), size: 18),
              onPressed: onToggleObscure,
            ),
            validator: (v) {
              if (v == null || v.isEmpty) return 'Password is required';
              if (isRegister && v.length < 8) return 'At least 8 characters';
              return null;
            }),
        const SizedBox(height: 24),

        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: loading ? null : onSubmit,
            child: loading
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : Text(isRegister ? 'Create account' : 'Sign in'),
          ),
        ),
        const SizedBox(height: 16),

        Center(
          child: GestureDetector(
            onTap: onToggleMode,
            child: RichText(
              text: TextSpan(
                style: const TextStyle(fontSize: 13, color: Color(0xFF888AAA)),
                children: [
                  TextSpan(text: isRegister ? 'Already have an account? ' : "Don't have an account? "),
                  TextSpan(
                    text: isRegister ? 'Sign in' : 'Register',
                    style: const TextStyle(color: Color(0xFF6C63FF), fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _field(TextEditingController ctrl, String label, IconData icon, {
    bool obscure = false, Widget? suffixIcon,
    TextInputType? keyboardType, String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: ctrl,
      obscureText: obscure,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 18, color: const Color(0xFF888AAA)),
        suffixIcon: suffixIcon,
      ),
    );
  }
}

// ── Small reusable widgets ─────────────────────────────────────────────────────
class _Logo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Container(
        width: 80, height: 80,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(colors: [Color(0xFF6C63FF), Color(0xFF4ECDC4)]),
          boxShadow: [BoxShadow(color: const Color(0xFF6C63FF).withOpacity(0.4), blurRadius: 24, spreadRadius: 2)],
        ),
        child: const Icon(Icons.rocket_launch, color: Colors.white, size: 40),
      ),
      const SizedBox(height: 20),
      const Text('AutoReach', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white, letterSpacing: -0.5)),
      const SizedBox(height: 8),
      const Text('Automated lead generation & cold email outreach',
          textAlign: TextAlign.center,
          style: TextStyle(color: Color(0xFF888AAA), fontSize: 13)),
    ]);
  }
}

class _GoogleIcon extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 20, height: 20,
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(4)),
      child: const Center(child: Text('G', style: TextStyle(color: Color(0xFF4285F4), fontSize: 13, fontWeight: FontWeight.bold))),
    );
  }
}
