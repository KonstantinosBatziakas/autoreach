import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services/settings_service.dart';
import '../services/auth_service.dart';
import '../widgets/app_drawer.dart';
import '../constants.dart';

const _baseUrl = kBaseUrl;

class OutreachScreen extends StatefulWidget {
  const OutreachScreen({super.key});
  @override
  State<OutreachScreen> createState() => _OutreachScreenState();
}

class _OutreachScreenState extends State<OutreachScreen> {
  bool _running = false;
  bool _stop = false;
  int _total = 0, _current = 0, _sent = 0, _errors = 0;
  String _status = '';
  final List<_LogEntry> _log = [];
  bool _done = false;
  String _lang = 'english';
  String _templateId = 'classic';

  void _addLog(String msg, {Color color = const Color(0xFF888AAA)}) {
    setState(() => _log.add(_LogEntry(msg, color)));
  }

  Future<List<Map<String, dynamic>>> _fetchLeads() async {
    final token = await AuthService.getToken();
    final resp = await http.get(
      Uri.parse('$_baseUrl/api/leads'),
      headers: token != null ? {'Authorization': 'Bearer $token'} : {},
    ).timeout(const Duration(seconds: 20));
    if (resp.statusCode == 302 || resp.statusCode == 401) {
      throw Exception('Not authenticated. Please log in.');
    }
    if (resp.statusCode != 200) {
      throw Exception('Server error ${resp.statusCode}');
    }
    final list = jsonDecode(resp.body) as List;
    return list.cast<Map<String, dynamic>>();
  }

  Future<String> _generateEmail(String apiKey, String name, String address, String senderName) async {
    final sign = 'Sign the email as: $senderName';
    final prompt = _lang == 'greek'
        ? 'Γράψε ένα σύντομο επαγγελματικό email για cold outreach προσφέροντας υπηρεσίες '
          'σχεδιασμού ιστοσελίδων και ψηφιακού μάρκετινγκ στην επιχείρηση $name που βρίσκεται '
          'στη διεύθυνση $address. Υπόγραψε ως: $senderName. Κάτω από 150 λέξεις. Επέστρεψε μόνο το κείμενο του email.'
        : 'Write a short professional cold outreach email offering web design and digital marketing '
          'services to $name located at $address. Under 150 words. $sign. Only return the email body.';

    final resp = await http.post(
      Uri.parse('https://api.groq.com/openai/v1/chat/completions'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $apiKey',
      },
      body: jsonEncode({
        'model': 'llama-3.1-8b-instant',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.7,
        'max_tokens': 300,
      }),
    ).timeout(const Duration(seconds: 30));

    if (resp.statusCode != 200) {
      final err = jsonDecode(resp.body);
      throw Exception(err['error']?['message'] ?? 'Groq error ${resp.statusCode}');
    }
    return (jsonDecode(resp.body)['choices'][0]['message']['content'] as String).trim();
  }

  Future<void> _sendEmail(String businessName, String email, String subject, String body, String senderName) async {
    final token      = await AuthService.getToken();
    final resendKey  = await SettingsService.getResendApiKey();
    final fromEmail  = await SettingsService.getFromEmail();
    final resp = await http.post(
      Uri.parse('$_baseUrl/api/send-email'),
      headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'business_name': businessName,
        'email': email,
        'subject': subject,
        'body': body,
        'resend_api_key': resendKey,
        'from_email': fromEmail.isNotEmpty ? fromEmail : 'onboarding@resend.dev',
        'template_id': _templateId,
        'sender_name': senderName,
      }),
    ).timeout(const Duration(seconds: 20));

    if (resp.statusCode != 200) {
      final err = jsonDecode(resp.body);
      throw Exception(err['error'] ?? 'Send error ${resp.statusCode}');
    }
  }

  Future<void> _runCampaign() async {
    final groqKey    = await SettingsService.getGroqApiKey();
    final resendKey  = await SettingsService.getResendApiKey();
    final senderName = await SettingsService.getSenderName();

    if (groqKey.isEmpty) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Set your Groq API key in Settings first.'),
        backgroundColor: Color(0xFFE74C3C),
      ));
      return;
    }
    if (resendKey.isEmpty) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Set your Resend API key in Settings first. Free at resend.com.'),
        backgroundColor: Color(0xFFE74C3C),
      ));
      return;
    }

    setState(() {
      _running = true;
      _stop = false;
      _done = false;
      _sent = 0;
      _errors = 0;
      _current = 0;
      _log.clear();
      _status = 'Fetching leads…';
    });

    List<Map<String, dynamic>> leads;
    try {
      leads = await _fetchLeads();
    } catch (e) {
      _addLog('Failed to fetch leads: $e', color: const Color(0xFFE74C3C));
      setState(() { _running = false; _status = 'Error'; });
      return;
    }

    if (leads.isEmpty) {
      _addLog('No unsent leads found. Add leads with emails first.', color: const Color(0xFFE0B84A));
      setState(() { _running = false; _status = 'Nothing to send.'; });
      return;
    }

    setState(() { _total = leads.length; _status = 'Running…'; });
    _addLog('Found ${leads.length} lead(s) to contact.', color: const Color(0xFF4ECDC4));

    for (int i = 0; i < leads.length; i++) {
      if (_stop) { _addLog('⏹ Stopped by user.', color: const Color(0xFFE0B84A)); break; }

      final lead = leads[i];
      final name    = lead['name'] as String? ?? '';
      final address = lead['address'] as String? ?? '';
      final email   = lead['email'] as String? ?? '';

      setState(() { _current = i + 1; _status = 'Generating email for $name…'; });
      _addLog('Generating email for $name…');

      String body;
      try {
        body = await _generateEmail(groqKey, name, address, senderName);
      } catch (e) {
        _addLog('  ✗ Groq error: $e', color: const Color(0xFFE74C3C));
        setState(() => _errors++);
        continue;
      }

      final subject = _lang == 'greek'
          ? 'Γρήγορη ερώτηση για $name'
          : 'Quick question for $name';

      try {
        await _sendEmail(name, email, subject, body, senderName);
        _addLog('  ✓ Sent to $email', color: const Color(0xFF7DD87D));
        setState(() => _sent++);
      } catch (e) {
        _addLog('  ✗ Send failed: $e', color: const Color(0xFFE74C3C));
        setState(() => _errors++);
      }

      await Future.delayed(const Duration(milliseconds: 1200));
    }

    setState(() {
      _running = false;
      _done = true;
      _status = 'Campaign complete — $_sent sent, $_errors error(s).';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Outreach')),
      drawer: const AppDrawer(),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Outreach Campaign',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
          const Text('AI-generated cold emails sent from your device',
              style: TextStyle(color: Color(0xFF888AAA))),
          const SizedBox(height: 16),

          // Info box
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF4ECDC4).withOpacity(0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF4ECDC4).withOpacity(0.3)),
            ),
            child: const Text(
              'Groq AI runs directly on your device — not through the server — so there are no IP restrictions. '
              'Make sure your Groq API key is set in Settings.',
              style: TextStyle(color: Color(0xFF888AAA), fontSize: 13),
            ),
          ),
          const SizedBox(height: 16),

          // Language selector
          if (!_running) ...[
            Card(child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(children: [
                const Text('Language:', style: TextStyle(color: Colors.white)),
                const SizedBox(width: 16),
                DropdownButton<String>(
                  value: _lang,
                  dropdownColor: const Color(0xFF1E1E2E),
                  style: const TextStyle(color: Colors.white),
                  onChanged: (v) => setState(() => _lang = v!),
                  items: const [
                    DropdownMenuItem(value: 'english', child: Text('English')),
                    DropdownMenuItem(value: 'greek',   child: Text('Greek')),
                  ],
                ),
              ]),
            )),
            const SizedBox(height: 16),
          ],

          // Template picker
          if (!_running) ...[
            Card(child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Email Template', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                const Text('Choose a visual style for your emails', style: TextStyle(color: Color(0xFF666888), fontSize: 12)),
                const SizedBox(height: 12),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final t in [
                    ('classic', 'Classic Black'),
                    ('clean',   'Clean White'),
                    ('purple',  'Bold Purple'),
                    ('warm',    'Warm Orange'),
                    ('plain',   'Plain Text'),
                  ])
                    GestureDetector(
                      onTap: () => setState(() => _templateId = t.$1),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: _templateId == t.$1 ? const Color(0xFF4ECDC4) : const Color(0xFF333355),
                            width: 2,
                          ),
                          color: _templateId == t.$1 ? const Color(0xFF4ECDC4).withOpacity(0.12) : Colors.transparent,
                        ),
                        child: Text(t.$2, style: TextStyle(
                          color: _templateId == t.$1 ? const Color(0xFF4ECDC4) : const Color(0xFF888AAA),
                          fontSize: 12,
                          fontWeight: _templateId == t.$1 ? FontWeight.bold : FontWeight.normal,
                        )),
                      ),
                    ),
                ]),
                const SizedBox(height: 8),
                const Text('💡 Plain Text has highest deliverability', style: TextStyle(color: Color(0xFF555577), fontSize: 11)),
              ]),
            )),
            const SizedBox(height: 16),
          ],

          // Start / Stop button
          Row(children: [
            if (!_running)
              ElevatedButton.icon(
                icon: const Icon(Icons.send),
                label: const Text('Start Campaign'),
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4ECDC4)),
                onPressed: _runCampaign,
              )
            else
              ElevatedButton.icon(
                icon: const Icon(Icons.stop),
                label: const Text('Stop'),
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFE74C3C)),
                onPressed: () => setState(() => _stop = true),
              ),
          ]),
          const SizedBox(height: 20),

          // Progress bar
          if (_running || _done) ...[
            if (_total > 0) ...[
              LinearProgressIndicator(
                value: _total > 0 ? _current / _total : null,
                backgroundColor: const Color(0xFF1A1A2E),
                valueColor: const AlwaysStoppedAnimation(Color(0xFF4ECDC4)),
              ),
              const SizedBox(height: 8),
              Text('$_current / $_total  •  $_sent sent  •  $_errors errors',
                  style: const TextStyle(color: Color(0xFF888AAA), fontSize: 13)),
              const SizedBox(height: 4),
            ],
            Text(_status, style: const TextStyle(color: Color(0xFF4ECDC4), fontSize: 13)),
            const SizedBox(height: 12),
          ],

          // Log
          if (_log.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF0D0D1A),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: _log.reversed.take(40).toList().reversed
                    .map((e) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Text(e.msg, style: TextStyle(color: e.color, fontSize: 12, fontFamily: 'monospace')),
                        ))
                    .toList(),
              ),
            ),

          // Done CTA
          if (_done) ...[
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                icon: const Icon(Icons.inbox),
                label: const Text('View Sent Emails'),
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF6C63FF)),
                onPressed: () => Navigator.pushReplacementNamed(context, '/sent'),
              ),
            ),
          ],
        ]),
      ),
    );
  }
}

class _LogEntry {
  final String msg;
  final Color color;
  const _LogEntry(this.msg, this.color);
}
