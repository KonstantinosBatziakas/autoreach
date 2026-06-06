import 'package:flutter/material.dart';
import '../services/settings_service.dart';
import '../widgets/app_drawer.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _googleKey  = TextEditingController();
  final _resendKey  = TextEditingController();
  final _fromEmail  = TextEditingController();
  final _groqKey    = TextEditingController();
  final _senderName = TextEditingController();
  bool _loaded = false, _saving = false, _showPasswords = false;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    _googleKey.text  = await SettingsService.getGoogleApiKey();
    _resendKey.text  = await SettingsService.getResendApiKey();
    _fromEmail.text  = await SettingsService.getFromEmail();
    _groqKey.text    = await SettingsService.getGroqApiKey();
    _senderName.text = await SettingsService.getSenderName();
    setState(() => _loaded = true);
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await SettingsService.setGoogleApiKey(_googleKey.text.trim());
    await SettingsService.setResendApiKey(_resendKey.text.trim());
    await SettingsService.setFromEmail(_fromEmail.text.trim());
    await SettingsService.setGroqApiKey(_groqKey.text.trim());
    await SettingsService.setSenderName(_senderName.text.trim());
    setState(() => _saving = false);
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Settings saved!'), backgroundColor: Color(0xFF4ECDC4)));
  }

  Widget _section(String title) => Padding(padding: const EdgeInsets.only(top: 8, bottom: 12), child: Text(title, style: const TextStyle(color: Color(0xFF6C63FF), fontWeight: FontWeight.bold, fontSize: 13, letterSpacing: 1)));
  Widget _field(TextEditingController c, String label, IconData icon, {bool obscure = false}) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: TextField(controller: c, obscureText: obscure, style: const TextStyle(color: Colors.white), decoration: InputDecoration(labelText: label, prefixIcon: Icon(icon, size: 18))),
  );

  @override
  Widget build(BuildContext context) {
    if (!_loaded) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        actions: [IconButton(icon: Icon(_showPasswords ? Icons.visibility_off : Icons.visibility), onPressed: () => setState(() => _showPasswords = !_showPasswords))],
      ),
      drawer: const AppDrawer(),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _section('General'),
          _field(_senderName, 'Your Name / Company Name', Icons.person),
          _section('Google Maps API'),
          _field(_googleKey, 'Google Maps API Key', Icons.map, obscure: !_showPasswords),
          _section('Resend (Email Sending)'),
          _field(_resendKey, 'Resend API Key (free at resend.com)', Icons.send, obscure: !_showPasswords),
          _field(_fromEmail, 'From Email (verified in Resend)', Icons.alternate_email),
          _section('Groq AI'),
          _field(_groqKey, 'Groq API Key', Icons.psychology, obscure: !_showPasswords),
          const SizedBox(height: 24),
          SizedBox(width: double.infinity, child: ElevatedButton.icon(
            icon: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.save),
            label: Text(_saving ? 'Saving...' : 'Save Settings'),
            onPressed: _saving ? null : _save,
          )),
        ]),
      ),
    );
  }
}
