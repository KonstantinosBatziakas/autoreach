import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../constants.dart';
import '../services/auth_service.dart';
import '../services/aria_prompt_service.dart';
import '../services/openai_compatible_endpoint.dart';
import '../services/settings_service.dart';
import 'moderation_queue_screen.dart';
import '../widgets/app_drawer.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _googleKey = TextEditingController();
  final _resendKey = TextEditingController();
  final _fromEmail = TextEditingController();
  final _groqKey = TextEditingController();
  final _ariaBaseUrl = TextEditingController();
  final _ariaModel = TextEditingController();
  final _ariaApiKey = TextEditingController();
  final _ariaPrompt = TextEditingController();
  final _senderName = TextEditingController();
  bool _loaded = false, _saving = false, _showPasswords = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    _googleKey.text = await SettingsService.getGoogleApiKey();
    _resendKey.text = await SettingsService.getResendApiKey();
    _fromEmail.text = await SettingsService.getFromEmail();
    _groqKey.text = await SettingsService.getGroqApiKey();
    _ariaBaseUrl.text = await SettingsService.getAriaApiBaseUrl();
    _ariaModel.text = await SettingsService.getAriaModel();
    _ariaApiKey.text = await SettingsService.getAriaApiKey();
    _ariaPrompt.text = await SettingsService.getAriaCustomPrompt();
    _senderName.text = await SettingsService.getSenderName();
    setState(() => _loaded = true);
  }

  Future<void> _save() async {
    String? ariaSettingsError =
        AriaPromptService.validateCustomPrompt(_ariaPrompt.text);
    if (ariaSettingsError == null) {
      try {
        OpenAiCompatibleEndpoint.chatCompletionsUri(_ariaBaseUrl.text);
      } on FormatException catch (error) {
        ariaSettingsError = error.message;
      }
    }
    if (ariaSettingsError == null && _ariaModel.text.trim().isEmpty) {
      ariaSettingsError = 'Enter a model ID for ARIA.';
    }
    setState(() => _saving = true);
    if (ariaSettingsError == null && _ariaPrompt.text.trim().isNotEmpty) {
      try {
        final token = await AuthService.getToken();
        if (token == null)
          throw Exception('Sign in again before saving an ARIA prompt.');
        final response = await http
            .post(
              Uri.parse('$kBaseUrl/api/moderation/check'),
              headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer $token'
              },
              body: jsonEncode({
                'checkpoint': 'save',
                'content_type': 'aria_prompt',
                'content': _ariaPrompt.text.trim()
              }),
            )
            .timeout(const Duration(seconds: 20));
        if (response.statusCode != 200) {
          final result = jsonDecode(response.body) as Map<String, dynamic>;
          throw Exception(
              result['error'] ?? 'The prompt was not cleared for saving.');
        }
      } catch (error) {
        setState(() => _saving = false);
        if (mounted)
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', '')),
            backgroundColor: Colors.red.shade700,
          ));
        return;
      }
    }
    await SettingsService.setGoogleApiKey(_googleKey.text.trim());
    await SettingsService.setResendApiKey(_resendKey.text.trim());
    await SettingsService.setFromEmail(_fromEmail.text.trim());
    await SettingsService.setGroqApiKey(_groqKey.text.trim());
    if (ariaSettingsError == null) {
      await SettingsService.setAriaApiBaseUrl(_ariaBaseUrl.text.trim());
      await SettingsService.setAriaModel(_ariaModel.text.trim());
      await SettingsService.setAriaApiKey(_ariaApiKey.text.trim());
      await SettingsService.setAriaCustomPrompt(_ariaPrompt.text.trim());
    }
    await SettingsService.setSenderName(_senderName.text.trim());
    setState(() => _saving = false);
    if (mounted)
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ariaSettingsError ?? 'Settings saved!'),
        backgroundColor: ariaSettingsError == null
            ? const Color(0xFF4ECDC4)
            : Colors.red.shade700,
      ));
  }

  Widget _section(String title) => Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 12),
      child: Text(title,
          style: const TextStyle(
              color: Color(0xFF6C63FF),
              fontWeight: FontWeight.bold,
              fontSize: 13,
              letterSpacing: 1)));
  Widget _field(TextEditingController c, String label, IconData icon,
          {bool obscure = false, int maxLines = 1}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: TextField(
            controller: c,
            obscureText: obscure,
            maxLines: obscure ? 1 : maxLines,
            minLines: maxLines > 1 ? 3 : 1,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
                labelText: label, prefixIcon: Icon(icon, size: 18))),
      );

  @override
  Widget build(BuildContext context) {
    if (!_loaded)
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        actions: [
          IconButton(
              icon: Icon(
                  _showPasswords ? Icons.visibility_off : Icons.visibility),
              onPressed: () => setState(() => _showPasswords = !_showPasswords))
        ],
      ),
      drawer: const AppDrawer(),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _section('General'),
          _field(_senderName, 'Your Name / Company Name', Icons.person),
          _section('Google Maps API'),
          _field(_googleKey, 'Google Maps API Key', Icons.map,
              obscure: !_showPasswords),
          _section('Resend (Email Sending)'),
          _field(_resendKey, 'Resend API Key (free at resend.com)', Icons.send,
              obscure: !_showPasswords),
          _field(_fromEmail, 'From Email (verified in Resend)',
              Icons.alternate_email),
          _section('Groq AI'),
          _field(_groqKey, 'Groq API Key', Icons.psychology,
              obscure: !_showPasswords),
          _section('ARIA Model (OpenAI-Compatible API)'),
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
                'Use Groq, OpenAI, OpenRouter, or another OpenAI-compatible chat API. Your key is stored on this device and sent directly to your selected provider.',
                style: TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
          ),
          _field(_ariaBaseUrl, 'API Base URL', Icons.link),
          _field(_ariaModel, 'Model ID', Icons.psychology_alt),
          _field(_ariaApiKey, 'ARIA Provider API Key', Icons.key,
              obscure: !_showPasswords),
          _field(_ariaPrompt, 'Custom ARIA Prompt (moderated)', Icons.edit_note,
              maxLines: 4),
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text(
                'Custom instructions are limited to 1,200 characters. Profanity and attempts to override ARIA’s rules are rejected; accepted preferences cannot override its built-in policy.',
                style: TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              icon: const Icon(Icons.rule),
              label: const Text('Review moderation queue'),
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const ModerationQueueScreen(),
              )),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                icon: _saving
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.save),
                label: Text(_saving ? 'Saving...' : 'Save Settings'),
                onPressed: _saving ? null : _save,
              )),
        ]),
      ),
    );
  }
}
