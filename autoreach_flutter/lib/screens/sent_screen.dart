import 'package:flutter/material.dart';
import '../services/storage_service.dart';
import '../models/sent_email.dart';
import '../widgets/app_drawer.dart';

class SentScreen extends StatefulWidget {
  const SentScreen({super.key});
  @override
  State<SentScreen> createState() => _SentScreenState();
}

class _SentScreenState extends State<SentScreen> {
  List<SentEmail> _sent = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async { setState(() => _loading = true); _sent = await StorageService.getSentEmails(); setState(() => _loading = false); }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Sent Emails')),
    drawer: const AppDrawer(),
    body: _loading ? const Center(child: CircularProgressIndicator())
        : _sent.isEmpty
            ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.mark_email_unread, size: 60, color: Color(0xFF444466)),
                const SizedBox(height: 16),
                const Text('No emails sent yet', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 24),
                ElevatedButton.icon(icon: const Icon(Icons.send), label: const Text('Start Campaign'), onPressed: () => Navigator.pushNamed(context, '/outreach')),
              ]))
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: _sent.length,
                  itemBuilder: (_, i) {
                    final s = _sent[i];
                    return Card(margin: const EdgeInsets.only(bottom: 8), child: ListTile(
                      leading: Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: const Color(0xFF6C63FF).withOpacity(0.15), shape: BoxShape.circle), child: const Icon(Icons.mark_email_read, color: Color(0xFF6C63FF), size: 20)),
                      title: Text(s.businessName, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                      subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(s.email, style: const TextStyle(color: Color(0xFF4ECDC4), fontSize: 12)),
                        Text(s.subject, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
                      ]),
                      trailing: Text(s.dateSent.length >= 10 ? s.dateSent.substring(0, 10) : s.dateSent, style: const TextStyle(color: Color(0xFF555577), fontSize: 11)),
                      isThreeLine: true,
                    ));
                  },
                ),
              ),
  );
}
