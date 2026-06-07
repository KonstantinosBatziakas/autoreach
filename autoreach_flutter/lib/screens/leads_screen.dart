import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import '../models/lead.dart';
import '../widgets/app_drawer.dart';

class LeadsScreen extends StatefulWidget {
  const LeadsScreen({super.key});
  @override
  State<LeadsScreen> createState() => _LeadsScreenState();
}

class _LeadsScreenState extends State<LeadsScreen> {
  List<Lead> _leads = [];
  bool _loading = true, _scraping = false;
  String _search = '';

  static const _stages = ['New', 'Contacted', 'Replied', 'Closed'];
  static const _stageColors = {
    'New':       Color(0xFF6C63FF),
    'Contacted': Color(0xFFFFD166),
    'Replied':   Color(0xFF4ECDC4),
    'Closed':    Color(0xFF27C93F),
  };

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      _leads = await ApiService.getAllLeads();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: const Color(0xFFFF6B6B)));
    }
    setState(() => _loading = false);
  }

  Future<void> _scrapeEmails() async {
    setState(() => _scraping = true);
    if (mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(const SnackBar(
          content: Text('Scraping emails on the server — this takes ~30 seconds...'),
          backgroundColor: Color(0xFF4ECDC4),
          duration: Duration(seconds: 35),
        ));
    }
    try {
      await ApiService.triggerScrape();
      // Wait for the background scrape to finish (it crawls websites, takes time)
      await Future.delayed(const Duration(seconds: 35));
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Scraping complete! Pull down to refresh.'),
          backgroundColor: Color(0xFF27C93F),
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(e.toString().contains('409') ? 'Scraping already in progress — please wait.' : 'Scrape error: $e'),
          backgroundColor: const Color(0xFFFF6B6B),
        ));
      }
    }
    setState(() => _scraping = false);
  }

  List<Lead> get _filtered {
    if (_search.isEmpty) return _leads;
    final q = _search.toLowerCase();
    return _leads.where((l) => l.name.toLowerCase().contains(q) || l.email.toLowerCase().contains(q)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;
    final withEmail = _leads.where((l) => l.email.isNotEmpty).length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Leads'),
        actions: [
          if (_scraping) const Padding(padding: EdgeInsets.all(16), child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)))
          else IconButton(icon: const Icon(Icons.web), tooltip: 'Scrape Emails', onPressed: _leads.isEmpty ? null : _scrapeEmails),
          IconButton(icon: const Icon(Icons.person_add), onPressed: () => Navigator.pushNamed(context, '/add_lead').then((_) => _load())),
        ],
      ),
      drawer: const AppDrawer(),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Row(children: [
            Expanded(child: TextField(
              onChanged: (v) => setState(() => _search = v),
              decoration: const InputDecoration(hintText: 'Search leads...', prefixIcon: Icon(Icons.search, size: 18), contentPadding: EdgeInsets.symmetric(vertical: 10)),
            )),
            const SizedBox(width: 12),
            TextButton.icon(icon: const Icon(Icons.search, size: 16), label: const Text('Google Maps'), onPressed: () => Navigator.pushNamed(context, '/find_leads').then((_) => _load())),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(children: [
            Text('${_leads.length} total', style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
            const Text('  ·  ', style: TextStyle(color: Color(0xFF555577))),
            Text('$withEmail with email', style: const TextStyle(color: Color(0xFF4ECDC4), fontSize: 12)),
            const Text('  ·  ', style: TextStyle(color: Color(0xFF555577))),
            Text('${_leads.length - withEmail} missing', style: const TextStyle(color: Color(0xFFFF6B6B), fontSize: 12)),
          ]),
        ),
        const Divider(color: Color(0xFF2A2A3E)),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : filtered.isEmpty
                  ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      const Icon(Icons.business, size: 60, color: Color(0xFF444466)),
                      const SizedBox(height: 16),
                      const Text('No leads yet', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 24),
                      ElevatedButton.icon(icon: const Icon(Icons.search), label: const Text('Find via Google Maps'), onPressed: () => Navigator.pushNamed(context, '/find_leads').then((_) => _load())),
                    ]))
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: filtered.length,
                        itemBuilder: (_, i) => _LeadCard(
                          lead: filtered[i],
                          stages: _stages,
                          stageColors: _stageColors,
                          onStageChanged: (stage) async {
                            await ApiService.updateLeadStage(filtered[i].name, stage);
                            await _load();
                          },
                        ),
                      ),
                    ),
        ),
      ]),
    );
  }
}

class _LeadCard extends StatelessWidget {
  final Lead lead;
  final List<String> stages;
  final Map<String, Color> stageColors;
  final ValueChanged<String> onStageChanged;
  const _LeadCard({required this.lead, required this.stages, required this.stageColors, required this.onStageChanged});

  @override
  Widget build(BuildContext context) {
    final stageColor = stageColors[lead.stage] ?? const Color(0xFF6C63FF);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(lead.name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15))),
            // Stage dropdown
            GestureDetector(
              onTap: () => showModalBottomSheet(
                context: context,
                backgroundColor: const Color(0xFF1E1E2E),
                shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
                builder: (_) => Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('Update Stage', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                    const SizedBox(height: 16),
                    ...stages.map((s) => ListTile(
                      leading: CircleAvatar(radius: 6, backgroundColor: stageColors[s]),
                      title: Text(s, style: TextStyle(color: s == lead.stage ? stageColors[s] : Colors.white)),
                      trailing: s == lead.stage ? const Icon(Icons.check, color: Color(0xFF4ECDC4)) : null,
                      onTap: () { Navigator.pop(context); onStageChanged(s); },
                    )),
                  ]),
                ),
              ),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: stageColor.withOpacity(0.15), borderRadius: BorderRadius.circular(20), border: Border.all(color: stageColor.withOpacity(0.4))),
                child: Text(lead.stage, style: TextStyle(color: stageColor, fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ),
          ]),
          if (lead.address.isNotEmpty) ...[
            const SizedBox(height: 4),
            Row(children: [const Icon(Icons.location_on, size: 12, color: Color(0xFF888AAA)), const SizedBox(width: 4), Expanded(child: Text(lead.address, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12)))]),
          ],
          const SizedBox(height: 8),
          Row(children: [
            if (lead.email.isNotEmpty)
              Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3), decoration: BoxDecoration(color: const Color(0xFF4ECDC4).withOpacity(0.15), borderRadius: BorderRadius.circular(20), border: Border.all(color: const Color(0xFF4ECDC4).withOpacity(0.4))), child: Text(lead.email, style: const TextStyle(color: Color(0xFF4ECDC4), fontSize: 11)))
            else
              Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3), decoration: BoxDecoration(color: const Color(0xFF444466).withOpacity(0.3), borderRadius: BorderRadius.circular(20)), child: const Text('No email', style: TextStyle(color: Color(0xFF888AAA), fontSize: 11))),
            const Spacer(),
            if (lead.website.isNotEmpty)
              GestureDetector(onTap: () => launchUrl(Uri.parse(lead.website), mode: LaunchMode.externalApplication), child: const Text('Visit', style: TextStyle(color: Color(0xFF6C63FF), fontSize: 12, decoration: TextDecoration.underline))),
          ]),
        ]),
      ),
    );
  }
}
