import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/lead.dart';
import '../widgets/app_drawer.dart';

class AddLeadScreen extends StatefulWidget {
  const AddLeadScreen({super.key});
  @override
  State<AddLeadScreen> createState() => _AddLeadScreenState();
}

class _AddLeadScreenState extends State<AddLeadScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _address = TextEditingController();
  final _phone = TextEditingController();
  final _website = TextEditingController();
  final _email = TextEditingController();
  bool _saving = false;

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    await ApiService.addLead(Lead(name: _name.text.trim(), address: _address.text.trim(), phone: _phone.text.trim(), website: _website.text.trim(), email: _email.text.trim()));
    setState(() => _saving = false);
    if (mounted) { ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Added ${_name.text}!'), backgroundColor: const Color(0xFF4ECDC4))); Navigator.pop(context); }
  }

  Widget _field(TextEditingController c, String label, {TextInputType? type, String? Function(String?)? validator}) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: TextFormField(controller: c, keyboardType: type, validator: validator, style: const TextStyle(color: Colors.white), decoration: InputDecoration(labelText: label)),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Add Lead')),
    drawer: const AppDrawer(),
    body: SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(key: _formKey, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Add a Business Lead', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
        const SizedBox(height: 24),
        _field(_name, 'Business Name *', validator: (v) => v!.isEmpty ? 'Required' : null),
        _field(_address, 'Address'),
        _field(_phone, 'Phone', type: TextInputType.phone),
        _field(_website, 'Website', type: TextInputType.url),
        _field(_email, 'Email', type: TextInputType.emailAddress),
        const SizedBox(height: 8),
        SizedBox(width: double.infinity, child: ElevatedButton.icon(
          icon: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.person_add),
          label: Text(_saving ? 'Saving...' : 'Add Lead'),
          onPressed: _saving ? null : _save,
        )),
      ])),
    ),
  );
}
