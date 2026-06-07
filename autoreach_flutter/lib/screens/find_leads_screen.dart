import 'package:flutter/material.dart';
import '../services/maps_service.dart';
import '../services/api_service.dart';
import '../models/lead.dart';
import '../widgets/app_drawer.dart';

class FindLeadsScreen extends StatefulWidget {
  const FindLeadsScreen({super.key});
  @override
  State<FindLeadsScreen> createState() => _FindLeadsScreenState();
}

class _FindLeadsScreenState extends State<FindLeadsScreen> {
  final _formKey = GlobalKey<FormState>();
  final _city = TextEditingController();
  final _type = TextEditingController();
  bool _loading = false;
  bool _missingKey = false;
  List<Lead>? _results;
  String? _error;

  Future<void> _search() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _loading = true; _results = null; _error = null; _missingKey = false; });
    try {
      final leads = await MapsService.findBusinesses(_city.text.trim(), _type.text.trim());
      final saved = await ApiService.addLeads(leads);
      setState(() { _results = leads; _loading = false; });
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Found ${leads.length} businesses, $saved saved to server.'), backgroundColor: const Color(0xFF4ECDC4)));
    } catch (e) {
      final msg = e.toString();
      final isMissingKey = msg.contains('GOOGLE_MAPS_API_KEY') || msg.contains('API key') || msg.contains('REQUEST_DENIED');
      setState(() {
        _error = isMissingKey
            ? 'Google Maps API key is missing or invalid. Please go to Settings and add your Google Maps API key.'
            : msg;
        _missingKey = isMissingKey;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Find Leads')),
    drawer: const AppDrawer(),
    body: SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(key: _formKey, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Find Businesses', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
        const Text('Search via Google Maps API', style: TextStyle(color: Color(0xFF888AAA))),
        const SizedBox(height: 24),
        TextFormField(
          controller: _city,
          maxLength: 100,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(labelText: 'City *', prefixIcon: Icon(Icons.location_city)),
          validator: (v) {
            if (v == null || v.trim().isEmpty) return 'Enter a city';
            if (v.trim().length > 100) return 'Max 100 characters';
            return null;
          },
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: _type,
          maxLength: 100,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(labelText: 'Business Type * (e.g. restaurants)', prefixIcon: Icon(Icons.business)),
          validator: (v) {
            if (v == null || v.trim().isEmpty) return 'Enter a business type';
            if (v.trim().length > 100) return 'Max 100 characters';
            return null;
          },
        ),
        const SizedBox(height: 24),
        SizedBox(width: double.infinity, child: ElevatedButton.icon(
          icon: _loading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.search),
          label: Text(_loading ? 'Searching...' : 'Search Google Maps'),
          onPressed: _loading ? null : _search,
        )),
        if (_error != null) ...[
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: const Color(0xFFFF6B6B).withOpacity(0.1), borderRadius: BorderRadius.circular(10), border: Border.all(color: const Color(0xFFFF6B6B).withOpacity(0.4))),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_error!, style: const TextStyle(color: Color(0xFFFF6B6B))),
              if (_missingKey) ...[
                const SizedBox(height: 10),
                SizedBox(width: double.infinity, child: OutlinedButton.icon(
                  icon: const Icon(Icons.settings, size: 16),
                  label: const Text('Go to Settings'),
                  style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFF4ECDC4), side: const BorderSide(color: Color(0xFF4ECDC4))),
                  onPressed: () => Navigator.pushReplacementNamed(context, '/settings'),
                )),
              ],
            ]),
          ),
        ],
        if (_results != null) ...[
          const SizedBox(height: 24),
          Text('${_results!.length} results found', style: const TextStyle(color: Color(0xFF4ECDC4), fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          ..._results!.take(10).map((l) => Card(child: ListTile(title: Text(l.name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)), subtitle: Text(l.address, style: const TextStyle(color: Color(0xFF888AAA), fontSize: 12))))),
          const SizedBox(height: 12),
          ElevatedButton.icon(icon: const Icon(Icons.people), label: const Text('View All Leads'), onPressed: () => Navigator.pushReplacementNamed(context, '/leads')),
        ],
      ])),
    ),
  );
}
