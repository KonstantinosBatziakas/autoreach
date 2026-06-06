import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/app_drawer.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key});
  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  Map<String, int> _stats = {};
  List<Map<String, dynamic>> _sent = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final results = await Future.wait([ApiService.getStats(), ApiService.getSentEmails()]);
      setState(() {
        _stats = results[0] as Map<String, int>;
        _sent  = results[1] as List<Map<String, dynamic>>;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    }
    setState(() => _loading = false);
  }

  int get _todayCount {
    final today = DateTime.now().toIso8601String().substring(0, 10);
    return _sent.where((s) => (s['date_sent'] as String? ?? '').startsWith(today)).length;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Report')),
    drawer: const AppDrawer(),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
            ? Center(child: Text(_error!, style: const TextStyle(color: Color(0xFFFF6B6B))))
            : RefreshIndicator(
                onRefresh: _load,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(20),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('Outreach Report', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
                    const SizedBox(height: 20),
                    Row(children: [
                      Expanded(child: _StatBox(label: 'Total Leads',  value: '${_stats['total_leads'] ?? 0}',    color: const Color(0xFF6C63FF))),
                      const SizedBox(width: 12),
                      Expanded(child: _StatBox(label: 'Emails Sent',  value: '${_stats['emails_sent'] ?? 0}',    color: const Color(0xFF4ECDC4))),
                    ]),
                    const SizedBox(height: 12),
                    Row(children: [
                      Expanded(child: _StatBox(label: 'Follow-ups',   value: '${_stats['followups_sent'] ?? 0}', color: const Color(0xFFFFD166))),
                      const SizedBox(width: 12),
                      Expanded(child: _StatBox(label: 'Replied',      value: '${_stats['replied'] ?? 0}',        color: const Color(0xFF27C93F))),
                    ]),
                    const SizedBox(height: 12),
                    Row(children: [
                      Expanded(child: _StatBox(label: 'Sent Today',   value: '$_todayCount',                     color: const Color(0xFFFF9F43))),
                      const SizedBox(width: 12),
                      Expanded(child: _StatBox(label: 'With Email',   value: '${_stats['leads_with_emails'] ?? 0}', color: const Color(0xFF888AAA))),
                    ]),
                    const SizedBox(height: 24),
                    const Text('Recent Sent Emails', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                    const SizedBox(height: 12),
                    if (_sent.isEmpty)
                      const Center(child: Padding(padding: EdgeInsets.all(32), child: Text('No emails sent yet', style: TextStyle(color: Color(0xFF888AAA)))))
                    else
                      ..._sent.take(50).map((s) {
                        final date = s['date_sent'] as String? ?? '';
                        return Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(color: const Color(0xFF1E1E2E), borderRadius: BorderRadius.circular(10)),
                          child: Row(children: [
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(s['business_name'] as String? ?? '', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                              Text(s['email'] as String? ?? '', style: const TextStyle(color: Color(0xFF4ECDC4), fontSize: 12)),
                              Text(s['subject'] as String? ?? '', style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
                            ])),
                            Text(date.length >= 10 ? date.substring(0, 10) : date, style: const TextStyle(color: Color(0xFF555577), fontSize: 11)),
                          ]),
                        );
                      }),
                  ]),
                ),
              ),
  );
}

class _StatBox extends StatelessWidget {
  final String label, value; final Color color;
  const _StatBox({required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(color: const Color(0xFF1E1E2E), borderRadius: BorderRadius.circular(14), border: Border.all(color: color.withOpacity(0.3))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(value, style: TextStyle(color: color, fontSize: 32, fontWeight: FontWeight.bold)),
      Text(label, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
    ]),
  );
}
