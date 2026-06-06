import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/app_drawer.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _totalLeads = 0, _leadsWithEmail = 0, _emailsSent = 0, _followups = 0, _replied = 0;
  bool _loading = true;
  String? _error;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final stats = await ApiService.getStats();
      setState(() {
        _totalLeads    = stats['total_leads']    ?? 0;
        _leadsWithEmail= stats['leads_with_emails'] ?? 0;
        _emailsSent    = stats['emails_sent']    ?? 0;
        _followups     = stats['followups_sent'] ?? 0;
        _replied       = stats['replied']        ?? 0;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      drawer: const AppDrawer(),
      body: RefreshIndicator(
        onRefresh: _load,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          child: _loading
            ? const Center(child: Padding(padding: EdgeInsets.only(top: 60), child: CircularProgressIndicator()))
            : _error != null
              ? Center(child: Padding(padding: const EdgeInsets.only(top: 40), child: Text(_error!, style: const TextStyle(color: Color(0xFFFF6B6B)))))
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('AutoReach', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
            const Text('Lead generation & email outreach', style: TextStyle(color: Color(0xFF888AAA), fontSize: 14)),
            const SizedBox(height: 24),
            Row(children: [
              Expanded(child: _Stat(label: 'Total Leads', value: '$_totalLeads', icon: Icons.people, color: const Color(0xFF6C63FF))),
              const SizedBox(width: 12),
              Expanded(child: _Stat(label: 'With Email', value: '$_leadsWithEmail', icon: Icons.email, color: const Color(0xFF4ECDC4))),
              const SizedBox(width: 12),
              Expanded(child: _Stat(label: 'Emails Sent', value: '$_emailsSent', icon: Icons.send, color: const Color(0xFFFFD166))),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: _Stat(label: 'Follow-ups', value: '$_followups', icon: Icons.repeat, color: const Color(0xFFFF9F43))),
              const SizedBox(width: 12),
              Expanded(child: _Stat(label: 'Replied', value: '$_replied', icon: Icons.reply, color: const Color(0xFF27C93F))),
              const SizedBox(width: 12),
              Expanded(child: _Stat(label: 'Remaining', value: '${_leadsWithEmail - _emailsSent < 0 ? 0 : _leadsWithEmail - _emailsSent}', icon: Icons.pending, color: const Color(0xFF888AAA))),
            ]),
            const SizedBox(height: 28),
            const Text('Quick Actions', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
            const SizedBox(height: 12),
            _Action(icon: Icons.search,     title: 'Find Leads',          subtitle: 'Search via Google Maps',          color: const Color(0xFF6C63FF), onTap: () => Navigator.pushNamed(context, '/find_leads')),
            _Action(icon: Icons.person_add, title: 'Add Lead Manually',   subtitle: 'Add a business by hand',          color: const Color(0xFF4ECDC4), onTap: () => Navigator.pushNamed(context, '/add_lead')),
            _Action(icon: Icons.send,       title: 'Run Outreach',        subtitle: 'Send AI-generated cold emails',   color: const Color(0xFFFFD166), onTap: () => Navigator.pushNamed(context, '/outreach')),
            _Action(icon: Icons.smart_toy,  title: 'Ask ARIA',            subtitle: 'Get help from your AI assistant', color: const Color(0xFF4ECDC4), onTap: () => Navigator.pushNamed(context, '/aria')),
            _Action(icon: Icons.bar_chart,  title: 'View Report',         subtitle: 'See your outreach stats',         color: const Color(0xFFFF6B6B), onTap: () => Navigator.pushNamed(context, '/report')),
          ]),
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label, value; final IconData icon; final Color color;
  const _Stat({required this.label, required this.value, required this.icon, required this.color});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(color: const Color(0xFF1E1E2E), borderRadius: BorderRadius.circular(14), border: Border.all(color: color.withOpacity(0.3))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: color, size: 22),
      const SizedBox(height: 10),
      Text(value, style: TextStyle(color: color, fontSize: 24, fontWeight: FontWeight.bold)),
      Text(label, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 11)),
    ]),
  );
}

class _Action extends StatelessWidget {
  final IconData icon; final String title, subtitle; final Color color; final VoidCallback onTap;
  const _Action({required this.icon, required this.title, required this.subtitle, required this.color, required this.onTap});
  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: ListTile(
      leading: Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: color.withOpacity(0.15), shape: BoxShape.circle), child: Icon(icon, color: color, size: 22)),
      title: Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      subtitle: Text(subtitle, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
      trailing: const Icon(Icons.arrow_forward_ios, color: Color(0xFF555577), size: 14),
      onTap: onTap,
    ),
  );
}
