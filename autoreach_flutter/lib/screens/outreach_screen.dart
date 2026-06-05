import 'package:flutter/material.dart';
import '../widgets/app_drawer.dart';

class OutreachScreen extends StatelessWidget {
  const OutreachScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Outreach')),
    drawer: const AppDrawer(),
    body: SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Outreach Campaign', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
        const Text('Send AI-generated cold emails to your leads', style: TextStyle(color: Color(0xFF888AAA))),
        const SizedBox(height: 20),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: const Color(0xFFFFD166).withOpacity(0.08), borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFFFFD166).withOpacity(0.3))),
          child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('⚠️ Before you start', style: TextStyle(color: Color(0xFFFFD166), fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            Text('Email sending from mobile requires your Gmail credentials and Groq API key set in Settings. For best results use the desktop app for sending campaigns.', style: TextStyle(color: Color(0xFF888AAA), fontSize: 13)),
          ]),
        ),
        const SizedBox(height: 20),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('How it works', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _Step('1', 'All leads with emails are loaded'),
          _Step('2', 'Groq AI (Llama 3.1) generates a unique email per business'),
          _Step('3', 'Email is sent via your Gmail account'),
          _Step('4', 'Sent records are logged'),
          _Step('5', 'Follow-ups sent automatically at +3, +7, +14 days'),
        ]))),
        const SizedBox(height: 24),
        SizedBox(width: double.infinity, child: ElevatedButton.icon(
          icon: const Icon(Icons.send),
          label: const Text('Use Desktop App to Send'),
          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4ECDC4)),
          onPressed: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Open the desktop app at autoreach.dev to run campaigns!'))),
        )),
      ]),
    ),
  );
}

class _Step extends StatelessWidget {
  final String number, text;
  const _Step(this.number, this.text);
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(width: 20, height: 20, decoration: BoxDecoration(color: const Color(0xFF6C63FF).withOpacity(0.3), shape: BoxShape.circle), alignment: Alignment.center, child: Text(number, style: const TextStyle(color: Color(0xFF6C63FF), fontSize: 11, fontWeight: FontWeight.bold))),
      const SizedBox(width: 10),
      Expanded(child: Text(text, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 13))),
    ]),
  );
}
